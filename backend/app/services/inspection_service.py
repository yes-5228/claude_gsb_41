"""巡检计划派发、任务执行与异常转单业务逻辑."""
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_

from ..domain import inspection as catalog
from ..domain.constants import (
    INSPECTION_CYCLE_LABELS,
    INSPECTION_RESULT_LABELS,
    INSPECTION_TASK_STATUS_LABELS,
    INSPECTION_TASK_TODO_STATUSES,
    WORK_ORDER_ACTIVE_STATUSES,
)
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import (
    InspectionPlan,
    InspectionTask,
    InspectionTaskItem,
    Station,
    WorkOrder,
)

CYCLE_CHOICES = tuple(INSPECTION_CYCLE_LABELS.keys())
RESULT_CHOICES = tuple(INSPECTION_RESULT_LABELS.keys())
TASK_STATUS_CHOICES = tuple(INSPECTION_TASK_STATUS_LABELS.keys())


def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _int_list(args, name):
    values = []
    for item in _split(args.get(name)):
        try:
            values.append(int(item))
        except ValueError:
            raise ValidationError("%s 参数必须为整数" % name, fields={name: "invalid_integer"})
    return values


# ---------------------------------------------------------------- 巡检项目录
def inspection_catalog():
    return {"items": catalog.all_items()}


# ---------------------------------------------------------------- 巡检计划
def plan_query(args):
    query = InspectionPlan.query
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        query = query.filter(InspectionPlan.name.like("%" + keyword + "%"))
    cycles = _split(args.get("cycle"))
    if cycles:
        query = query.filter(InspectionPlan.cycle.in_(cycles))
    if str(args.get("enabled", "")).strip() != "":
        enabled = str(args.get("enabled")).strip().lower() in {"1", "true", "yes"}
        query = query.filter(InspectionPlan.enabled.is_(enabled))
    return query.order_by(InspectionPlan.next_run_date.asc(), InspectionPlan.id.desc())


def get_plan(plan_id):
    plan = db.session.get(InspectionPlan, plan_id)
    if plan is None:
        raise NotFoundError("巡检计划不存在: id=%s" % plan_id)
    return plan


def _validate_station_ids(station_ids):
    station_ids = list(dict.fromkeys(int(item) for item in station_ids))
    if not station_ids:
        raise ValidationError("请至少选择一个监测点", fields={"station_ids": "empty"})
    found = {row.id for row in Station.query.filter(Station.id.in_(station_ids)).all()}
    missing = [item for item in station_ids if item not in found]
    if missing:
        raise ValidationError(
            "监测点不存在: %s" % ", ".join(str(item) for item in missing),
            fields={"station_ids": "not_found"},
        )
    return station_ids


def _validate_item_codes(item_codes):
    item_codes = list(dict.fromkeys(str(item).strip() for item in item_codes if str(item).strip()))
    if not item_codes:
        raise ValidationError("请至少选择一个巡检项", fields={"items": "empty"})
    unknown = [code for code in item_codes if code not in catalog.known_codes()]
    if unknown:
        raise ValidationError(
            "巡检项不存在: %s" % ", ".join(unknown), fields={"items": "unknown"}
        )
    return item_codes


def _load_stations(station_ids):
    return Station.query.filter(Station.id.in_(station_ids)).order_by(Station.code.asc()).all()


def create_plan(data):
    station_ids = _validate_station_ids(data["station_ids"])
    item_codes = _validate_item_codes(data["items"])
    if data["start_date"] < date.today():
        raise ValidationError("开始日期不能早于今天", fields={"start_date": "past"})
    if data.get("end_date") and data["end_date"] < data["start_date"]:
        raise ValidationError("结束日期不能早于开始日期", fields={"end_date": "before_start"})

    plan = InspectionPlan(
        name=data["name"],
        cycle=data["cycle"],
        items=item_codes,
        enabled=data.get("enabled", True),
        start_date=data["start_date"],
        next_run_date=data["start_date"],
        end_date=data.get("end_date"),
        inspector=data.get("inspector"),
        remark=data.get("remark"),
    )
    plan.stations = _load_stations(station_ids)
    db.session.add(plan)
    db.session.commit()
    return plan


def update_plan(plan, data):
    if "name" in data:
        plan.name = data["name"]
    if "cycle" in data:
        plan.cycle = data["cycle"]
    if "inspector" in data:
        plan.inspector = data["inspector"]
    if "remark" in data:
        plan.remark = data["remark"]
    if "enabled" in data:
        plan.enabled = data["enabled"]
    if "end_date" in data:
        plan.end_date = data["end_date"]
    if "start_date" in data:
        plan.start_date = data["start_date"]
        if plan.next_run_date < data["start_date"]:
            plan.next_run_date = data["start_date"]
    if "station_ids" in data:
        station_ids = _validate_station_ids(data["station_ids"])
        plan.stations = _load_stations(station_ids)
    if "items" in data:
        plan.items = _validate_item_codes(data["items"])
    db.session.commit()
    return plan


def delete_plan(plan):
    task_count = InspectionTask.query.filter_by(plan_id=plan.id).count()
    db.session.delete(plan)
    db.session.commit()
    return {"tasks_kept": task_count}


# ---------------------------------------------------------------- 周期推进
def advance_cycle_date(current, cycle, ref=None):
    """Next dispatch date for a recurring plan."""
    ref = ref or date.today()
    if cycle == "daily":
        return current + timedelta(days=1)
    if cycle == "weekly":
        return current + timedelta(days=7)
    if cycle == "monthly":
        year, month = current.year, current.month + 1
        if month > 12:
            year, month = year + 1, 1
        day = min(current.day, 28)
        return date(year, month, day)
    return current  # 单次计划不推进


def _make_code(prefix, today):
    startswith = prefix + today.strftime("%Y%m%d")
    count = (
        db.session.query(InspectionTask if prefix == "XJ" else WorkOrder)
        .filter((InspectionTask if prefix == "XJ" else WorkOrder).code.like(startswith + "%"))
        .count()
    )
    return "%s%s%03d" % (prefix, today.strftime("%Y%m%d"), count + 1)


def _instantiate_task(plan, station, due_date, items=None, inspector=None):
    """Create one inspection task for one station.

    ``plan`` may be ``None`` (manual ad-hoc task), in which case ``items``
    must carry the selected catalog codes.
    """
    item_codes = items if plan is None or getattr(plan, "id", None) is None else plan.items
    task = InspectionTask(
        code=_make_code("XJ", due_date),
        plan_id=getattr(plan, "id", None),
        station_id=station.id,
        status="pending",
        due_date=due_date,
        inspector=inspector or getattr(plan, "inspector", None),
        items_snapshot=catalog.snapshot(item_codes),
    )
    db.session.add(task)
    db.session.flush()  # 取得 task.id, 便于明细外键关联
    for item in task.items_snapshot:
        db.session.add(
            InspectionTaskItem(
                task_id=task.id,
                item_code=item["code"],
                item_name=item["name"],
                category=item["category"],
            )
        )
    return task


# ---------------------------------------------------------------- 派发
def dispatch_due_plans(today=None):
    """Dispatch pending -> in_progress... 的周期任务: 到期计划按点位生成任务."""
    today = today or date.today()
    plans = (
        InspectionPlan.query
        .filter(InspectionPlan.enabled.is_(True))
        .filter(InspectionPlan.next_run_date <= today)
        .order_by(InspectionPlan.next_run_date.asc())
        .all()
    )
    created_tasks = []
    dispatched_plans = []
    for plan in plans:
        stations = [s for s in plan.stations if s.status != "offline"]
        for station in stations:
            exists = InspectionTask.query.filter_by(
                plan_id=plan.id, station_id=station.id, due_date=plan.next_run_date
            ).first()
            if exists:
                continue
            created_tasks.append(_instantiate_task(plan, station, plan.next_run_date))
        if plan.cycle == "once":
            plan.enabled = False
        else:
            plan.next_run_date = advance_cycle_date(plan.next_run_date, plan.cycle, today)
        dispatched_plans.append(plan.id)

    db.session.commit()
    mark_overdue(today)
    return {
        "dispatched_plan_count": len(dispatched_plans),
        "task_count": len(created_tasks),
        "task_ids": [task.id for task in created_tasks],
        "tasks": [task.to_dict() for task in created_tasks],
        "as_of": today.isoformat(),
    }


def dispatch_plan_now(plan, today=None):
    """Manually dispatch a plan immediately (regardless of next_run_date)."""
    today = today or date.today()
    created = []
    stations = [s for s in plan.stations if s.status != "offline"]
    skipped = []
    for station in stations:
        exists = InspectionTask.query.filter_by(
            plan_id=plan.id, station_id=station.id, due_date=today
        ).first()
        if exists:
            skipped.append(station.id)
            continue
        created.append(_instantiate_task(plan, station, today))
    db.session.commit()
    mark_overdue(today)
    return {
        "task_count": len(created),
        "skipped_station_ids": skipped,
        "tasks": [task.to_dict() for task in created],
    }


def create_manual_task(data):
    station = db.session.get(Station, data["station_id"])
    if station is None:
        raise NotFoundError("监测点不存在: id=%s" % data["station_id"])
    item_codes = _validate_item_codes(data["items"])
    due_date = data.get("due_date") or date.today()

    task = _instantiate_task(
        plan=None, station=station, due_date=due_date,
        items=item_codes, inspector=data.get("inspector"),
    )
    db.session.commit()
    mark_overdue(due_date)
    return task


def mark_overdue(today=None):
    """Flag untouched tasks whose due date has passed as overdue (mutates+flush)."""
    today = today or date.today()
    stale = (
        InspectionTask.query
        .filter(InspectionTask.status.in_(("pending", "in_progress")))
        .filter(InspectionTask.due_date < today)
        .all()
    )
    for task in stale:
        task.status = "overdue"
    db.session.flush()
    return len(stale)


# ---------------------------------------------------------------- 任务查询
def task_query(args):
    query = db.session.query(InspectionTask).join(Station, InspectionTask.station_id == Station.id)
    statuses = _split(args.get("status"))
    if statuses:
        query = query.filter(InspectionTask.status.in_(statuses))
    station_ids = _int_list(args, "station_id")
    if station_ids:
        query = query.filter(InspectionTask.station_id.in_(station_ids))
    areas = _split(args.get("area"))
    if areas:
        query = query.filter(Station.area.in_(areas))
    if _split(args.get("plan_id")):
        query = query.filter(InspectionTask.plan_id.in_(_int_list(args, "plan_id")))
    inspector = (args.get("inspector") or "").strip()
    if inspector:
        query = query.filter(InspectionTask.inspector == inspector)
    keyword = (args.get("keyword") or "").strip()
    if keyword:
        like = "%" + keyword + "%"
        query = query.filter(
            or_(Station.name.like(like), Station.code.like(like), InspectionTask.code.like(like))
        )
    date_from = args.get("date_from")
    if date_from:
        from ..utils.validation import parse_date
        query = query.filter(InspectionTask.due_date >= parse_date(date_from, "开始日期"))
    date_to = args.get("date_to")
    if date_to:
        from ..utils.validation import parse_date
        query = query.filter(InspectionTask.due_date <= parse_date(date_to, "截止日期"))

    sort_key = {"due_date": InspectionTask.due_date, "created_at": InspectionTask.created_at}.get(
        args.get("sort"), InspectionTask.due_date
    )
    primary = sort_key.desc() if (args.get("order") or "desc") == "desc" else sort_key.asc()
    return query.order_by(primary, InspectionTask.id.desc())


def get_task(task_id):
    task = db.session.get(InspectionTask, task_id)
    if task is None:
        raise NotFoundError("巡检任务不存在: id=%s" % task_id)
    return task


def get_task_item(item_id):
    item = db.session.get(InspectionTaskItem, item_id)
    if item is None:
        raise NotFoundError("巡检项不存在: id=%s" % item_id)
    return item


# ---------------------------------------------------------------- 任务执行
def start_task(task, inspector=None):
    if task.status in ("completed", "abnormal"):
        raise ConflictError("该巡检任务已办结, 不能再次开始")
    if task.status == "pending" or task.status == "overdue":
        task.status = "in_progress"
        task.started_at = datetime.now()
    if inspector:
        task.inspector = inspector
    db.session.commit()
    return task


def record_item(task, item, result, remark=None, inspector=None):
    """Record one inspection item result; task transitions to in_progress automatically."""
    if task.status in ("completed", "abnormal"):
        raise ConflictError("巡检任务已办结, 不能再登记结果")
    if result not in RESULT_CHOICES:
        raise ValidationError(
            "巡检结果取值不合法, 可选: %s" % ", ".join(RESULT_CHOICES),
            fields={"result": "unknown"},
        )
    if result == "abnormal" and not (remark or "").strip():
        raise ValidationError("巡检结果为异常时必须填写异常说明", fields={"remark": "required"})

    item.result = result
    item.remark = (remark or "").strip() or None
    item.inspector = inspector or task.inspector
    item.checked_at = datetime.now()
    if task.status in ("pending", "overdue"):
        task.status = "in_progress"
        task.started_at = task.started_at or datetime.now()
    if inspector and not task.inspector:
        task.inspector = inspector

    _refresh_task_counters(task)
    db.session.commit()
    return item


def _refresh_task_counters(task):
    task.abnormal_count = sum(1 for row in task.task_items if row.result == "abnormal")


def submit_task(task, summary=None, inspector=None):
    """Finish a task: every item must have a result; abnormal tasks keep status='abnormal'."""
    pending_items = [row for row in task.task_items if row.result is None]
    if pending_items:
        raise ConflictError(
            "还有 %d 个巡检项未登记结果, 无法提交" % len(pending_items)
        )
    _refresh_task_counters(task)
    task.status = "abnormal" if task.abnormal_count else "completed"
    task.finished_at = datetime.now()
    task.started_at = task.started_at or datetime.now()
    task.summary = (summary or "").strip() or task.summary
    if inspector:
        task.inspector = inspector
    db.session.commit()
    return task


# ---------------------------------------------------------------- 异常转单
def convert_item_to_work_order(item, data=None):
    """Turn one abnormal inspection item into a repair work order."""
    data = data or {}
    task = item.task
    if item.result != "abnormal":
        raise ConflictError("仅巡检结果为“异常”的巡检项可以转维修工单")
    if item.work_order is not None and item.work_order.status in WORK_ORDER_ACTIVE_STATUSES:
        raise ConflictError("该异常项已存在进行中的维修工单: %s" % item.work_order.code)

    from . import work_order_service

    order = work_order_service.create_work_order(
        station_id=task.station_id,
        title=data.get("title") or "%s · %s" % (task.station.name, item.item_name),
        description=data.get("description")
        or ("巡检任务 %s 发现异常: %s" % (task.code, item.remark or item.item_name)),
        priority=data.get("priority") or "normal",
        reporter=data.get("reporter") or task.inspector,
        assignee=data.get("assignee"),
        source="inspection",
        task_item=item,
        inspection_task=task,
        due_date=data.get("due_date"),
        commit=False,
    )
    db.session.commit()
    return order


# ---------------------------------------------------------------- 统计
def task_summary(args=None):
    """Counters for the inspection work bench."""
    args = args or {}
    by_status = {
        status: {"key": status, "label": label, "count": 0}
        for status, label in INSPECTION_TASK_STATUS_LABELS.items()
    }
    base_filters = []
    areas = _split(args.get("area"))
    if areas:
        base_filters.append(Station.area.in_(areas))
    station_ids = _int_list(args, "station_id")
    if station_ids:
        base_filters.append(InspectionTask.station_id.in_(station_ids))

    query = (
        db.session.query(InspectionTask.status, func.count(InspectionTask.id))
        .join(Station, InspectionTask.station_id == Station.id)
        .filter(*base_filters)
        .group_by(InspectionTask.status)
        .all()
    )
    for status, count in query:
        if status in by_status:
            by_status[status]["count"] = int(count)

    todo = sum(by_status[status]["count"] for status in INSPECTION_TASK_TODO_STATUSES)
    abnormal_open_orders = (
        WorkOrder.query.filter(WorkOrder.status.in_(WORK_ORDER_ACTIVE_STATUSES)).count()
    )
    due_today = (
        InspectionTask.query.filter(InspectionTask.due_date == date.today())
        .filter(InspectionTask.status.in_(("pending", "in_progress", "overdue")))
        .count()
    )
    return {
        "total": sum(item["count"] for item in by_status.values()),
        "todo": todo,
        "due_today": due_today,
        "active_work_orders": abnormal_open_orders,
        "by_status": list(by_status.values()),
    }


def todo_counts():
    """Lightweight badge counters consumed by the navigation / overview."""
    today = date.today()
    pending = InspectionTask.query.filter(
        InspectionTask.status.in_(("pending", "overdue"))
    ).count()
    in_progress = InspectionTask.query.filter(InspectionTask.status == "in_progress").count()
    open_orders = WorkOrder.query.filter(
        WorkOrder.status.in_(WORK_ORDER_ACTIVE_STATUSES)
    ).count()
    due_today = (
        InspectionTask.query
        .filter(InspectionTask.due_date <= today)
        .filter(InspectionTask.status.in_(("pending", "overdue")))
        .count()
    )
    return {
        "pending_tasks": pending,
        "in_progress_tasks": in_progress,
        "todo_tasks": pending + in_progress,
        "active_work_orders": open_orders,
        "due_tasks": due_today,
    }
