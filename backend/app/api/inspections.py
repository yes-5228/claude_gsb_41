"""运维巡检 API: 巡检计划、周期派发、巡检任务执行、异常转单."""
from datetime import date

from flask import Blueprint, request

from ..domain.constants import (
    INSPECTION_CYCLE_LABELS,
    INSPECTION_RESULT_LABELS,
    INSPECTION_TASK_STATUS_LABELS,
)
from ..services import inspection_service, station_service, work_order_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator, parse_date
from .helpers import json_payload

bp = Blueprint("inspections", __name__)


# ---------------------------------------------------------------- 目录/选项
@bp.get("/catalog")
def inspection_catalog():
    return inspection_service.inspection_catalog()


@bp.get("/options")
def inspection_options():
    return {
        "cycles": [{"value": k, "label": v} for k, v in INSPECTION_CYCLE_LABELS.items()],
        "task_statuses": [
            {"value": k, "label": v} for k, v in INSPECTION_TASK_STATUS_LABELS.items()
        ],
        "results": [{"value": k, "label": v} for k, v in INSPECTION_RESULT_LABELS.items()],
        "stations": station_service.option_list(),
        "areas": station_service.area_list(),
    }


@bp.get("/todo-counts")
def todo_counts():
    return inspection_service.todo_counts()


# ---------------------------------------------------------------- 巡检计划
@bp.get("/plans", strict_slashes=False)
def list_plans():
    query = inspection_service.plan_query(request.args)
    result = paginate_query(query, lambda row: row.to_dict(include_stations=True))
    result["areas"] = station_service.area_list()
    return result


@bp.post("/plans", strict_slashes=False)
def create_plan():
    data = json_payload()
    payload = _validate_plan(data)
    plan = inspection_service.create_plan(payload)
    return plan.to_dict(include_stations=True), 201


@bp.get("/plans/<int:plan_id>")
def get_plan(plan_id):
    return inspection_service.get_plan(plan_id).to_dict(include_stations=True)


@bp.put("/plans/<int:plan_id>")
def update_plan(plan_id):
    plan = inspection_service.get_plan(plan_id)
    data = json_payload()
    payload = _validate_plan(data, partial=True)
    return inspection_service.update_plan(plan, payload).to_dict(include_stations=True)


@bp.delete("/plans/<int:plan_id>")
def delete_plan(plan_id):
    plan = inspection_service.get_plan(plan_id)
    result = inspection_service.delete_plan(plan)
    return {"id": plan_id, "removed": result}


@bp.post("/plans/<int:plan_id>/dispatch")
def dispatch_plan(plan_id):
    """手动立即派发一次计划."""
    plan = inspection_service.get_plan(plan_id)
    return inspection_service.dispatch_plan_now(plan)


@bp.post("/dispatch-due")
def dispatch_due():
    """执行到期周期计划的自动派发 (可由定时任务/运维手动触发)."""
    return inspection_service.dispatch_due_plans()


# ---------------------------------------------------------------- 巡检任务
@bp.get("/tasks", strict_slashes=False)
def list_tasks():
    # 查询前先把过期待处理任务刷新为“已逾期”, 保证列表/待办口径一致
    inspection_service.mark_overdue()
    query = inspection_service.task_query(request.args)
    result = paginate_query(query, lambda row: row.to_dict())
    result["summary"] = inspection_service.task_summary(request.args)
    return result


@bp.get("/tasks/summary")
def tasks_summary():
    inspection_service.mark_overdue()
    return inspection_service.task_summary(request.args)


@bp.post("/tasks", strict_slashes=False)
def create_task():
    data = json_payload()
    validator = Validator(data)
    station_id = validator.number("station_id", "监测点", required=True, minimum=1)
    validator.date_field("due_date", "应检日期")
    validator.text("inspector", "巡检人", required=False, max_length=64)
    validator.raise_if_invalid("巡检任务信息不合法")
    items = _require_items(data)
    task = inspection_service.create_manual_task(
        {
            "station_id": int(station_id),
            "items": items,
            "due_date": validator.cleaned.get("due_date"),
            "inspector": validator.cleaned.get("inspector"),
        }
    )
    return task.to_dict(include_items=True), 201


@bp.get("/tasks/<int:task_id>")
def get_task(task_id):
    task = inspection_service.get_task(task_id)
    return task.to_dict(include_items=True, include_plan=True)


@bp.post("/tasks/<int:task_id>/start")
def start_task(task_id):
    task = inspection_service.get_task(task_id)
    data = json_payload() if request.get_json(silent=True) is not None else {}
    inspector = (data.get("inspector") or "").strip() or None
    return inspection_service.start_task(task, inspector=inspector).to_dict(include_items=True)


@bp.put("/tasks/<int:task_id>/items/<int:item_id>")
def record_item(task_id, item_id):
    task = inspection_service.get_task(task_id)
    item = inspection_service.get_task_item(item_id)
    if item.task_id != task.id:
        from ..errors import ValidationError
        raise ValidationError("巡检项不属于该任务", fields={"item_id": "mismatch"})
    data = json_payload()
    validator = Validator(data)
    result = validator.choice(
        "result", "巡检结果", choices=tuple(INSPECTION_RESULT_LABELS.keys()), required=True
    )
    remark = validator.text("remark", "情况说明", required=False, max_length=1000)
    inspector = validator.text("inspector", "巡检人", required=False, max_length=64)
    validator.raise_if_invalid("巡检结果不合法")
    updated = inspection_service.record_item(
        task, item, result=result, remark=remark, inspector=inspector
    )
    return updated.to_dict()


@bp.post("/tasks/<int:task_id>/submit")
def submit_task(task_id):
    task = inspection_service.get_task(task_id)
    data = json_payload() if request.get_json(silent=True) is not None else {}
    validator = Validator(data)
    summary = validator.text("summary", "巡检总结", required=False, max_length=1000)
    inspector = validator.text("inspector", "巡检人", required=False, max_length=64)
    validator.raise_if_invalid()
    return inspection_service.submit_task(
        task, summary=summary, inspector=inspector
    ).to_dict(include_items=True)


@bp.post("/tasks/<int:task_id>/items/<int:item_id>/convert")
def convert_item(task_id, item_id):
    """异常巡检项一键转维修工单, 同时把点位台账置为维护中."""
    task = inspection_service.get_task(task_id)
    item = inspection_service.get_task_item(item_id)
    if item.task_id != task.id:
        from ..errors import ValidationError
        raise ValidationError("巡检项不属于该任务", fields={"item_id": "mismatch"})
    data = json_payload() if request.get_json(silent=True) is not None else {}
    validator = Validator(data)
    validator.text("title", "工单标题", required=False, max_length=160)
    validator.text("description", "异常描述", required=False, max_length=1000)
    validator.choice(
        "priority", "优先级",
        choices=tuple(work_order_service.PRIORITY_CHOICES), required=False, default="normal",
    )
    validator.text("reporter", "报修人", required=False, max_length=64)
    validator.text("assignee", "维修负责人", required=False, max_length=64)
    validator.date_field("due_date", "要求完成日期")
    cleaned = validator.raise_if_invalid("工单信息不合法")
    order = inspection_service.convert_item_to_work_order(item, cleaned)
    return order.to_dict(), 201


# ---------------------------------------------------------------- 参数校验
def _require_items(data):
    items = data.get("items")
    if not isinstance(items, list) or not items:
        from ..errors import ValidationError
        raise ValidationError("请至少选择一个巡检项", fields={"items": "empty"})
    return items


def _validate_plan(data, partial=False):
    validator = Validator(data)
    validator.text("name", "计划名称", required=not partial, max_length=120)
    validator.choice(
        "cycle", "巡检周期", choices=tuple(INSPECTION_CYCLE_LABELS.keys()),
        required=False, default="weekly",
    )
    validator.date_field("start_date", "开始日期", required=not partial)
    validator.date_field("end_date", "结束日期")
    validator.text("inspector", "默认巡检人", required=False, max_length=64)
    validator.text("remark", "备注", required=False, max_length=500)
    if "enabled" in data:
        validator.boolean("enabled", True)
    cleaned = validator.raise_if_invalid("巡检计划不合法")

    if partial:
        # 未提交的字段保持原值, 仅保留请求中显式出现的键
        cleaned = {key: value for key, value in cleaned.items() if key in data}

    # 显式提交才更新关联, 未提交时保持原值
    if "station_ids" in data:
        cleaned["station_ids"] = [
            int(item) for item in _require_id_list(data, "station_ids", "监测点")
        ]
    elif not partial:
        cleaned["station_ids"] = [
            int(item) for item in _require_id_list(data, "station_ids", "监测点")
        ]
    if "items" in data or not partial:
        cleaned["items"] = _require_items(data)
    return cleaned


def _require_id_list(data, field, label):
    value = data.get(field)
    if not isinstance(value, list) or not value:
        from ..errors import ValidationError
        raise ValidationError("请至少选择一个%s" % label, fields={field: "empty"})
    try:
        return [int(item) for item in value]
    except (TypeError, ValueError):
        from ..errors import ValidationError
        raise ValidationError("%s必须为整数 ID 列表" % label, fields={field: "invalid"})
