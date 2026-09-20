"""维修工单业务逻辑: 报修、接单、处理完成并回写台账运行状态."""
from datetime import datetime

from sqlalchemy import func, or_

from ..domain.constants import REPAIR_PRIORITY_LABELS, REPAIR_STATUS_LABELS, STATION_STATUS_LABELS
from ..errors import NotFoundError, ValidationError
from ..extensions import db
from ..models import RepairOrder, Station

PRIORITY_CHOICES = tuple(REPAIR_PRIORITY_LABELS.keys())
STATUS_CHOICES = tuple(REPAIR_STATUS_LABELS.keys())
OPEN_STATUSES = ("open", "processing")


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _next_code(now=None):
    """工单编号: WX + 日期 + 当日序号, 如 WX20260920-003."""
    now = now or datetime.now()
    prefix = "WX%s" % now.strftime("%Y%m%d")
    last = (
        RepairOrder.query.filter(RepairOrder.code.like(prefix + "-%"))
        .order_by(RepairOrder.code.desc())
        .first()
    )
    sequence = int(last.code.rsplit("-", 1)[1]) + 1 if last else 1
    return "%s-%03d" % (prefix, sequence)


def get_repair(repair_id):
    repair = db.session.get(RepairOrder, repair_id)
    if repair is None:
        raise NotFoundError("维修工单不存在: id=%s" % repair_id)
    return repair


def repair_query(args):
    query = db.session.query(RepairOrder).join(Station, RepairOrder.station_id == Station.id)

    statuses = _split(args.get("status"))
    if statuses:
        query = query.filter(RepairOrder.status.in_(statuses))
    priorities = _split(args.get("priority"))
    if priorities:
        query = query.filter(RepairOrder.priority.in_(priorities))
    station_id = (args.get("station_id") or "").strip()
    if station_id:
        try:
            query = query.filter(RepairOrder.station_id == int(station_id))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid_integer"})
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(
                RepairOrder.code.like(like),
                RepairOrder.title.like(like),
                Station.name.like(like),
                Station.code.like(like),
            )
        )
    if str(args.get("open_only", "")).strip().lower() in {"1", "true", "yes"}:
        query = query.filter(RepairOrder.status.in_(OPEN_STATUSES))

    order = (args.get("order") or "desc").lower()
    primary = RepairOrder.id.asc() if order == "asc" else RepairOrder.id.desc()
    return query.order_by(primary)


def create_repair(station, data, inspection_task=None, commit=True):
    """创建维修工单; 设备异常期间台账运行状态置为“维护中”(原为运行中时).

    `commit=False` 时由调用方统一提交, 用于巡检完成 + 转工单的单事务场景.
    """
    repair = RepairOrder(
        code=_next_code(),
        station_id=station.id,
        inspection_task_id=inspection_task.id if inspection_task else None,
        title=data["title"],
        description=(data.get("description") or "").strip() or None,
        priority=data.get("priority") or "medium",
        reporter=(data.get("reporter") or "").strip() or None,
        handler=(data.get("handler") or "").strip() or None,
        station_status_before=station.status,
    )
    if repair.priority not in PRIORITY_CHOICES:
        raise ValidationError(
            "工单优先级取值不合法, 可选: %s" % ", ".join(PRIORITY_CHOICES),
            fields={"priority": "unknown"},
        )
    if repair.handler:
        repair.status = "processing"
    if station.status == "active":
        station.status = "maintenance"
    db.session.add(repair)
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return repair


def claim_repair(repair, handler=None):
    """接单: 待处理 -> 处理中."""
    if repair.status != "open":
        raise ValidationError(
            "当前状态为“%s”, 仅待处理工单可以接单"
            % REPAIR_STATUS_LABELS.get(repair.status, repair.status),
            fields={"status": "invalid_transition"},
        )
    repair.status = "processing"
    if handler:
        repair.handler = handler
    if not repair.handler:
        raise ValidationError("请填写处理人", fields={"handler": "required"})
    db.session.commit()
    return repair


def resolve_repair(repair, resolution, handler=None, station_status_after="active"):
    """处理完成: 记录处理结果并回写台账运行状态, 保证台账与工单状态一致."""
    if repair.status not in OPEN_STATUSES:
        raise ValidationError(
            "工单已处理完毕, 当前状态: %s" % REPAIR_STATUS_LABELS.get(repair.status, repair.status),
            fields={"status": "invalid_transition"},
        )
    resolution = (resolution or "").strip()
    if not resolution:
        raise ValidationError("请填写处理结果", fields={"resolution": "required"})
    if station_status_after not in STATION_STATUS_LABELS:
        raise ValidationError(
            "台账运行状态取值不合法, 可选: %s" % ", ".join(STATION_STATUS_LABELS),
            fields={"station_status_after": "unknown"},
        )
    repair.status = "resolved"
    repair.resolution = resolution
    repair.resolved_at = datetime.now()
    if handler:
        repair.handler = handler
    if not repair.handler:
        raise ValidationError("请填写处理人", fields={"handler": "required"})
    # 回写台账运行状态
    repair.station_status_after = station_status_after
    if repair.station:
        repair.station.status = station_status_after
    db.session.commit()
    return repair


def close_repair(repair, resolution=None, station_status_after=None):
    """关闭工单: 无需维修或误报时使用, 可选择同时回写台账状态."""
    if repair.status not in OPEN_STATUSES:
        raise ValidationError(
            "工单已处理完毕, 当前状态: %s" % REPAIR_STATUS_LABELS.get(repair.status, repair.status),
            fields={"status": "invalid_transition"},
        )
    repair.status = "closed"
    repair.closed_at = datetime.now()
    if (resolution or "").strip():
        repair.resolution = resolution.strip()
    if station_status_after:
        if station_status_after not in STATION_STATUS_LABELS:
            raise ValidationError(
                "台账运行状态取值不合法, 可选: %s" % ", ".join(STATION_STATUS_LABELS),
                fields={"station_status_after": "unknown"},
            )
        repair.station_status_after = station_status_after
        if repair.station:
            repair.station.status = station_status_after
    db.session.commit()
    return repair


def summary(args=None):
    """工单统计: 待办列表与卡片共用同一数据源, 保证状态一致."""
    query = repair_query(args or {})
    subquery = query.with_entities(RepairOrder.status, RepairOrder.priority).subquery()

    by_status = {
        status: {"key": status, "label": label, "count": 0}
        for status, label in REPAIR_STATUS_LABELS.items()
    }
    for status, count in db.session.query(subquery.c.status, func.count()).group_by(subquery.c.status).all():
        if status in by_status:
            by_status[status]["count"] = int(count)

    open_count = by_status["open"]["count"] + by_status["processing"]["count"]
    urgent_open = (
        db.session.query(func.count())
        .select_from(RepairOrder)
        .filter(RepairOrder.status.in_(OPEN_STATUSES), RepairOrder.priority.in_(("high", "urgent")))
        .scalar()
    )
    return {
        "total": sum(item["count"] for item in by_status.values()),
        "open": open_count,
        "urgent_open": int(urgent_open or 0),
        "by_status": list(by_status.values()),
    }
