"""维修工单: 状态流转与台账运行状态回写 (状态一致性的单一收口)."""
from datetime import date, datetime

from sqlalchemy import or_

from ..domain.constants import (
    STATION_STATUS_LABELS,
    WORK_ORDER_ACTIVE_STATUSES,
    WORK_ORDER_PRIORITY_LABELS,
    WORK_ORDER_SOURCE_LABELS,
    WORK_ORDER_STATUS_LABELS,
)
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import InspectionTask, Station, WorkOrder
from .inspection_service import _make_code

STATUS_CHOICES = tuple(WORK_ORDER_STATUS_LABELS.keys())
PRIORITY_CHOICES = tuple(WORK_ORDER_PRIORITY_LABELS.keys())

# 允许的工单状态流转
TRANSITIONS = {
    "open": {"processing", "cancelled"},
    "processing": {"resolved", "cancelled"},
    "resolved": {"closed", "processing"},
    "closed": set(),
    "cancelled": set(),
}


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def get_work_order(order_id):
    order = db.session.get(WorkOrder, order_id)
    if order is None:
        raise NotFoundError("维修工单不存在: id=%s" % order_id)
    return order


def work_order_query(args):
    query = db.session.query(WorkOrder).join(Station, WorkOrder.station_id == Station.id)
    statuses = _split(args.get("status"))
    if statuses:
        query = query.filter(WorkOrder.status.in_(statuses))
    sources = _split(args.get("source"))
    if sources:
        query = query.filter(WorkOrder.source.in_(sources))
    priorities = _split(args.get("priority"))
    if priorities:
        query = query.filter(WorkOrder.priority.in_(priorities))
    station_ids_raw = _split(args.get("station_id"))
    if station_ids_raw:
        try:
            station_ids = [int(item) for item in station_ids_raw]
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid"})
        query = query.filter(WorkOrder.station_id.in_(station_ids))
    areas = _split(args.get("area"))
    if areas:
        query = query.filter(Station.area.in_(areas))
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(
                WorkOrder.title.like(like),
                WorkOrder.code.like(like),
                Station.name.like(like),
                WorkOrder.assignee.like(like),
            )
        )
    return query.order_by(WorkOrder.reported_at.desc(), WorkOrder.id.desc())


def create_work_order(
    station_id,
    title,
    description=None,
    priority="normal",
    reporter=None,
    assignee=None,
    source="manual",
    task_item=None,
    inspection_task=None,
    due_date=None,
    commit=True,
):
    station = db.session.get(Station, station_id)
    if station is None:
        raise NotFoundError("监测点不存在: id=%s" % station_id)
    if priority not in PRIORITY_CHOICES:
        raise ValidationError("工单优先级取值不合法", fields={"priority": "unknown"})
    if source not in WORK_ORDER_SOURCE_LABELS:
        raise ValidationError("工单来源取值不合法", fields={"source": "unknown"})

    if task_item is not None:
        # 同一异常项不允许存在两张进行中的工单
        existing = WorkOrder.query.filter_by(task_item_id=task_item.id).first()
        if existing and existing.status in WORK_ORDER_ACTIVE_STATUSES:
            raise ConflictError("该异常项已存在进行中的维修工单: %s" % existing.code)

    order = WorkOrder(
        code=_make_code("WX", date.today()),
        station_id=station_id,
        task_item_id=task_item.id if task_item else None,
        inspection_task_id=(
            inspection_task.id if inspection_task
            else task_item.task_id if task_item else None
        ),
        source=source,
        title=title,
        description=description,
        priority=priority,
        status="open",
        reporter=reporter,
        assignee=assignee,
        reported_at=datetime.now(),
        due_date=due_date,
    )
    db.session.add(order)
    db.session.flush()
    _sync_station_status(station)
    if commit:
        db.session.commit()
    return order


def transition(order, target, assignee=None, resolution=None, restore_status=None):
    """Move a work order to the next lifecycle status and write back the ledger."""
    if target not in STATUS_CHOICES:
        raise ValidationError("工单状态取值不合法", fields={"status": "unknown"})
    if target == order.status:
        return order
    if target not in TRANSITIONS.get(order.status, set()):
        raise ConflictError(
            "工单当前为“%s”, 不能变更为“%s”"
            % (WORK_ORDER_STATUS_LABELS[order.status], WORK_ORDER_STATUS_LABELS[target])
        )

    now = datetime.now()
    if target == "processing":
        order.started_at = now
        if assignee:
            order.assignee = assignee
    elif target == "resolved":
        if not (resolution or order.resolution or "").strip():
            raise ValidationError("维修完成时必须填写处理说明", fields={"resolution": "required"})
        order.resolution = (resolution or order.resolution).strip()
        order.resolved_at = now
        if restore_status:
            order.restore_status = restore_status
    elif target == "closed":
        order.closed_at = now
    elif target == "cancelled":
        order.closed_at = now
        order.resolution = (resolution or order.resolution or "工单取消").strip()

    order.status = target
    db.session.flush()
    _sync_station_status(order.station)
    db.session.commit()
    return order


def assign(order, assignee):
    order.assignee = assignee
    db.session.commit()
    return order


# ---------------------------------------------------------------- 台账回写
def _sync_station_status(station):
    """Single source of truth for the ledger status vs. active work orders.

    - 点位存在进行中的工单 (open/processing) -> maintenance 维护中
    - 最后一张工单办结后 -> 恢复为运行中 (除非点位已被人工停用 offline)
    """
    if station is None or station.status == "offline":
        return
    active = (
        WorkOrder.query
        .filter(WorkOrder.station_id == station.id)
        .filter(WorkOrder.status.in_(WORK_ORDER_ACTIVE_STATUSES))
        .count()
    )
    if active:
        if station.status != "maintenance":
            station.status = "maintenance"
    elif station.status == "maintenance":
        station.status = "active"


def summary(args=None):
    args = args or {}
    query = work_order_query(args)
    subquery = query.with_entities(WorkOrder.id, WorkOrder.status, WorkOrder.priority,
                                   WorkOrder.source).subquery()
    by_status = {
        status: {"key": status, "label": label, "count": 0}
        for status, label in WORK_ORDER_STATUS_LABELS.items()
    }
    for status, count in (
        db.session.query(subquery.c.status, db.func.count()).group_by(subquery.c.status).all()
    ):
        if status in by_status:
            by_status[status]["count"] = int(count)
    active = by_status["open"]["count"] + by_status["processing"]["count"]
    return {
        "total": sum(item["count"] for item in by_status.values()),
        "active": active,
        "by_status": list(by_status.values()),
        "station_status_labels": STATION_STATUS_LABELS,
    }
