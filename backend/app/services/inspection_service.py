"""运维巡检业务逻辑: 计划管理、按周期派发、逐项记录结果、待办聚合."""
import calendar
import json
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_

from ..domain.constants import (
    INSPECTION_CYCLE_LABELS,
    INSPECTION_ITEM_RESULT_LABELS,
    INSPECTION_TASK_STATUS_LABELS,
)
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import InspectionItemResult, InspectionPlan, InspectionTask, RepairOrder, Station
from . import repair_service

CYCLE_CHOICES = tuple(INSPECTION_CYCLE_LABELS.keys())
TASK_STATUS_CHOICES = tuple(INSPECTION_TASK_STATUS_LABELS.keys())
ITEM_RESULT_CHOICES = tuple(INSPECTION_ITEM_RESULT_LABELS.keys())
OPEN_TASK_STATUSES = ("pending", "in_progress")


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


# ---- 周期计算 -------------------------------------------------------------
def current_period(cycle, today=None):
    """返回 (周期标识, 应完成日期); 周期标识用于按周期幂等派发."""
    today = today or date.today()
    if cycle == "weekly":
        iso_year, iso_week, _ = today.isocalendar()
        due = today + timedelta(days=6 - today.weekday())  # 本周日
        return "%d-W%02d" % (iso_year, iso_week), due
    if cycle == "monthly":
        due = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        return "%d-%02d" % (today.year, today.month), due
    if cycle == "quarterly":
        quarter = (today.month - 1) // 3 + 1
        end_month = quarter * 3
        due = date(today.year, end_month, calendar.monthrange(today.year, end_month)[1])
        return "%d-Q%d" % (today.year, quarter), due
    raise ValidationError("巡检周期取值不合法, 可选: %s" % ", ".join(CYCLE_CHOICES))


# ---- 巡检计划 -------------------------------------------------------------
def plan_query(args):
    query = db.session.query(InspectionPlan).join(Station, InspectionPlan.station_id == Station.id)
    station_id = (args.get("station_id") or "").strip()
    if station_id:
        try:
            query = query.filter(InspectionPlan.station_id == int(station_id))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid_integer"})
    cycles = _split(args.get("cycle"))
    if cycles:
        query = query.filter(InspectionPlan.cycle.in_(cycles))
    active = (args.get("active") or "").strip().lower()
    if active in {"1", "true", "yes"}:
        query = query.filter(InspectionPlan.active.is_(True))
    elif active in {"0", "false", "no"}:
        query = query.filter(InspectionPlan.active.is_(False))
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(InspectionPlan.name.like(like), Station.name.like(like), Station.code.like(like))
        )
    return query.order_by(InspectionPlan.id.asc())


def get_plan(plan_id):
    plan = db.session.get(InspectionPlan, plan_id)
    if plan is None:
        raise NotFoundError("巡检计划不存在: id=%s" % plan_id)
    return plan


def validate_plan_payload(data, partial=False):
    from ..utils.validation import Validator

    validator = Validator(data)
    validator.text("name", "计划名称", required=not partial, max_length=120)
    validator.choice(
        "cycle", "巡检周期", choices=CYCLE_CHOICES, required=False, default="monthly"
    )
    validator.text("assignee", "默认巡检人", required=False, max_length=64)
    validator.text("remark", "备注", required=False, max_length=1000)
    validator.boolean("active", default=True)
    cleaned = validator.raise_if_invalid("巡检计划不合法")

    if "station_id" in data or not partial:
        raw = data.get("station_id")
        try:
            station_id = int(raw)
        except (TypeError, ValueError):
            raise ValidationError("请选择监测点", fields={"station_id": "required"})
        station = db.session.get(Station, station_id)
        if station is None:
            raise ValidationError("监测点不存在: id=%s" % station_id, fields={"station_id": "not_found"})
        cleaned["station_id"] = station_id

    if "items" in data or not partial:
        items = data.get("items")
        if not isinstance(items, list) or not items:
            raise ValidationError("请至少勾选一个巡检项", fields={"items": "empty"})
        cleaned_items = []
        for item in items:
            name = str(item).strip()
            if not name:
                continue
            if len(name) > 120:
                raise ValidationError("巡检项名称过长", fields={"items": "too_long"})
            cleaned_items.append(name)
        if not cleaned_items:
            raise ValidationError("请至少勾选一个巡检项", fields={"items": "empty"})
        cleaned["items"] = json.dumps(cleaned_items, ensure_ascii=False)

    if partial:
        cleaned = {key: value for key, value in cleaned.items() if key in data}
    return cleaned


def create_plan(data):
    plan = InspectionPlan(**data)
    db.session.add(plan)
    db.session.commit()
    return plan


def update_plan(plan, data):
    for field, value in data.items():
        setattr(plan, field, value)
    db.session.commit()
    return plan


def delete_plan(plan):
    task_count = InspectionTask.query.filter_by(plan_id=plan.id).count()
    if task_count:
        raise ConflictError("该计划已派发 %d 条巡检任务, 请改为停用" % task_count)
    db.session.delete(plan)
    db.session.commit()


# ---- 任务派发 -------------------------------------------------------------
def _create_task_from_plan(plan, period_key, due_date, now=None):
    task = InspectionTask(
        plan_id=plan.id,
        station_id=plan.station_id,
        period_key=period_key,
        title="%s (%s)" % (plan.name, period_key),
        cycle=plan.cycle,
        due_date=due_date,
        status="pending",
        assignee=plan.assignee,
        dispatched_at=now or datetime.now(),
    )
    task.items = [InspectionItemResult(item_name=name) for name in plan.item_list()]
    db.session.add(task)
    return task


def dispatch_plan(plan, today=None):
    """按计划周期派发本期任务; 同一周期重复派发会被跳过, 保证幂等."""
    if not plan.active:
        raise ValidationError("计划已停用, 无法派发巡检任务", fields={"active": "disabled"})
    period_key, due_date = current_period(plan.cycle, today)
    existing = InspectionTask.query.filter_by(plan_id=plan.id, period_key=period_key).first()
    if existing:
        return existing, False
    task = _create_task_from_plan(plan, period_key, due_date)
    db.session.commit()
    return task, True


def dispatch_all(today=None):
    """一键派发: 为所有启用中的计划生成本期巡检任务."""
    plans = InspectionPlan.query.filter_by(active=True).order_by(InspectionPlan.id.asc()).all()
    created, skipped = [], []
    for plan in plans:
        period_key, due_date = current_period(plan.cycle, today)
        exists = InspectionTask.query.filter_by(plan_id=plan.id, period_key=period_key).first()
        if exists:
            skipped.append({"plan_id": plan.id, "task_id": exists.id, "period_key": period_key})
            continue
        created.append(_create_task_from_plan(plan, period_key, due_date))
    db.session.commit()
    return {
        "created_count": len(created),
        "skipped_count": len(skipped),
        "created": [task.to_dict() for task in created],
        "skipped": skipped,
    }


def create_adhoc_task(data):
    """手工临时派发: 不依赖计划, 直接给点位下派巡检任务."""
    from ..utils.validation import Validator

    validator = Validator(data)
    title = validator.text("title", "任务标题", required=False, max_length=160)
    validator.text("assignee", "巡检人", required=False, max_length=64)
    validator.text("remark", "备注", required=False, max_length=1000)
    due_date = validator.date_field("due_date", "应完成日期")
    validator.raise_if_invalid("巡检任务不合法")

    try:
        station_id = int(data.get("station_id"))
    except (TypeError, ValueError):
        raise ValidationError("请选择监测点", fields={"station_id": "required"})
    station = db.session.get(Station, station_id)
    if station is None:
        raise ValidationError("监测点不存在: id=%s" % station_id, fields={"station_id": "not_found"})

    items = data.get("items")
    if not isinstance(items, list) or not [str(i).strip() for i in items if str(i).strip()]:
        raise ValidationError("请至少勾选一个巡检项", fields={"items": "empty"})

    task = InspectionTask(
        plan_id=None,
        station_id=station.id,
        period_key="",
        title=title or "%s 临时巡检" % station.name,
        cycle="monthly",
        due_date=due_date,
        status="pending",
        assignee=(data.get("assignee") or "").strip() or None,
        remark=(data.get("remark") or "").strip() or None,
        dispatched_at=datetime.now(),
    )
    task.items = [
        InspectionItemResult(item_name=str(item).strip())
        for item in items
        if str(item).strip()
    ]
    db.session.add(task)
    db.session.commit()
    return task


# ---- 任务执行 -------------------------------------------------------------
def task_query(args):
    query = db.session.query(InspectionTask).join(Station, InspectionTask.station_id == Station.id)
    statuses = _split(args.get("status"))
    if statuses:
        query = query.filter(InspectionTask.status.in_(statuses))
    cycles = _split(args.get("cycle"))
    if cycles:
        query = query.filter(InspectionTask.cycle.in_(cycles))
    station_id = (args.get("station_id") or "").strip()
    if station_id:
        try:
            query = query.filter(InspectionTask.station_id == int(station_id))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid_integer"})
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(InspectionTask.title.like(like), Station.name.like(like), Station.code.like(like))
        )
    if str(args.get("overdue", "")).strip().lower() in {"1", "true", "yes"}:
        query = query.filter(
            InspectionTask.status.in_(OPEN_TASK_STATUSES),
            InspectionTask.due_date < date.today(),
        )
    if str(args.get("open_only", "")).strip().lower() in {"1", "true", "yes"}:
        query = query.filter(InspectionTask.status.in_(OPEN_TASK_STATUSES))
    return query.order_by(
        InspectionTask.due_date.is_(None), InspectionTask.due_date.asc(), InspectionTask.id.desc()
    )


def get_task(task_id):
    task = db.session.get(InspectionTask, task_id)
    if task is None:
        raise NotFoundError("巡检任务不存在: id=%s" % task_id)
    return task


def start_task(task, executor=None):
    if task.status != "pending":
        raise ValidationError(
            "当前状态为“%s”, 仅待执行任务可以开始"
            % INSPECTION_TASK_STATUS_LABELS.get(task.status, task.status),
            fields={"status": "invalid_transition"},
        )
    task.status = "in_progress"
    task.started_at = datetime.now()
    if executor:
        task.executor = executor
    db.session.commit()
    return task


def complete_task(task, items, executor=None, summary=None, repair_data=None):
    """提交巡检结果: 逐项记录; 存在异常项时可同事务生成维修工单并更新台账.

    任务状态、巡检项结果、维修工单、台账运行状态在同一事务内提交,
    任一环节失败整体回滚, 保证台账 / 巡检记录 / 待办列表一致.
    """
    if task.status not in OPEN_TASK_STATUSES:
        raise ValidationError(
            "任务已结束, 当前状态: %s"
            % INSPECTION_TASK_STATUS_LABELS.get(task.status, task.status),
            fields={"status": "invalid_transition"},
        )
    if not isinstance(items, list) or not items:
        raise ValidationError("请逐项填写巡检结果", fields={"items": "empty"})

    payload_by_id = {}
    for entry in items:
        if not isinstance(entry, dict):
            raise ValidationError("巡检项结果格式不正确", fields={"items": "invalid"})
        try:
            payload_by_id[int(entry.get("id"))] = entry
        except (TypeError, ValueError):
            raise ValidationError("巡检项结果缺少 id", fields={"items": "invalid"})

    errors = {}
    abnormal_names = []
    for item in task.items:
        entry = payload_by_id.get(item.id)
        if entry is None:
            errors["items"] = "存在未提交的巡检项, 请逐项记录"
            continue
        result = str(entry.get("result") or "").strip()
        note = str(entry.get("note") or "").strip()
        if result not in ("normal", "abnormal", "skipped"):
            errors["items"] = "巡检项“%s”尚未填写有效结果" % item.item_name
            continue
        if result == "abnormal" and not note:
            errors["items"] = "巡检项“%s”判定异常时必须填写异常说明" % item.item_name
            continue
        item.result = result
        item.note = note or None
        if result == "abnormal":
            abnormal_names.append(item.item_name)
    if errors:
        raise ValidationError(errors["items"], fields=errors)

    task.executor = (executor or "").strip() or task.executor or task.assignee
    if not task.executor:
        raise ValidationError("请填写巡检人", fields={"executor": "required"})
    task.summary = (summary or "").strip() or None
    task.result = "abnormal" if abnormal_names else "normal"
    task.status = "completed"
    task.completed_at = datetime.now()
    if task.started_at is None:
        task.started_at = task.completed_at

    repair = None
    if repair_data:
        if not abnormal_names:
            raise ValidationError("未发现异常项, 无需生成维修工单", fields={"repair": "no_abnormal"})
        repair_payload = dict(repair_data)
        if not (repair_payload.get("title") or "").strip():
            repair_payload["title"] = "%s 设备异常维修" % task.station.name
        if not (repair_payload.get("description") or "").strip():
            repair_payload["description"] = "巡检异常项: %s" % "、".join(abnormal_names)
        if not (repair_payload.get("reporter") or "").strip():
            repair_payload["reporter"] = task.executor
        repair = repair_service.create_repair(
            task.station, repair_payload, inspection_task=task, commit=False
        )

    db.session.commit()
    return task, repair


def cancel_task(task, reason=None):
    if task.status not in OPEN_TASK_STATUSES:
        raise ValidationError(
            "任务已结束, 当前状态: %s"
            % INSPECTION_TASK_STATUS_LABELS.get(task.status, task.status),
            fields={"status": "invalid_transition"},
        )
    task.status = "cancelled"
    if (reason or "").strip():
        task.remark = ((task.remark or "") + " " if task.remark else "") + "取消原因: " + reason.strip()
    db.session.commit()
    return task


# ---- 待办与统计 -----------------------------------------------------------
def todo():
    """待办列表: 未完成巡检任务 + 未结维修工单, 与台账状态同源."""
    today = date.today()
    tasks = (
        InspectionTask.query.filter(InspectionTask.status.in_(OPEN_TASK_STATUSES))
        .order_by(InspectionTask.due_date.is_(None), InspectionTask.due_date.asc(), InspectionTask.id.asc())
        .all()
    )
    repairs = (
        RepairOrder.query.filter(RepairOrder.status.in_(repair_service.OPEN_STATUSES))
        .order_by(RepairOrder.id.desc())
        .all()
    )
    return {
        "tasks": [task.to_dict() for task in tasks],
        "repairs": [repair.to_dict() for repair in repairs],
        "task_count": len(tasks),
        "repair_count": len(repairs),
        "overdue_count": sum(1 for task in tasks if task.due_date and task.due_date < today),
    }


def summary():
    today = date.today()
    by_status = {
        status: {"key": status, "label": label, "count": 0}
        for status, label in INSPECTION_TASK_STATUS_LABELS.items()
    }
    for status, count in (
        db.session.query(InspectionTask.status, func.count())
        .group_by(InspectionTask.status)
        .all()
    ):
        if status in by_status:
            by_status[status]["count"] = int(count)

    open_count = by_status["pending"]["count"] + by_status["in_progress"]["count"]
    overdue = (
        db.session.query(func.count())
        .select_from(InspectionTask)
        .filter(
            InspectionTask.status.in_(OPEN_TASK_STATUSES),
            InspectionTask.due_date < today,
        )
        .scalar()
    )
    abnormal = (
        db.session.query(func.count())
        .select_from(InspectionTask)
        .filter(InspectionTask.result == "abnormal")
        .scalar()
    )
    return {
        "plan_total": InspectionPlan.query.count(),
        "plan_active": InspectionPlan.query.filter_by(active=True).count(),
        "task_total": sum(item["count"] for item in by_status.values()),
        "task_open": open_count,
        "task_overdue": int(overdue or 0),
        "task_abnormal": int(abnormal or 0),
        "by_status": list(by_status.values()),
        "repair": repair_service.summary(),
    }
