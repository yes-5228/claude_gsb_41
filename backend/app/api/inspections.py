"""运维巡检 API: 计划 / 派发 / 任务执行 / 待办."""
from flask import Blueprint, request

from ..domain.constants import (
    INSPECTION_CYCLE_LABELS,
    INSPECTION_ITEM_CATALOG,
    INSPECTION_ITEM_RESULT_LABELS,
    INSPECTION_TASK_STATUS_LABELS,
)
from ..services import inspection_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator
from .helpers import json_payload

bp = Blueprint("inspections", __name__)


# ---- 选项与统计 -----------------------------------------------------------
@bp.get("/options")
def inspection_options():
    return {
        "cycles": [{"value": key, "label": label} for key, label in INSPECTION_CYCLE_LABELS.items()],
        "task_statuses": [
            {"value": key, "label": label} for key, label in INSPECTION_TASK_STATUS_LABELS.items()
        ],
        "item_results": [
            {"value": key, "label": label} for key, label in INSPECTION_ITEM_RESULT_LABELS.items()
        ],
        "item_catalog": list(INSPECTION_ITEM_CATALOG),
    }


@bp.get("/summary")
def inspection_summary():
    return inspection_service.summary()


@bp.get("/todo")
def inspection_todo():
    """待办列表: 待执行/执行中任务 + 待处理/处理中工单."""
    return inspection_service.todo()


# ---- 巡检计划 -------------------------------------------------------------
@bp.get("/plans")
def list_plans():
    query = inspection_service.plan_query(request.args)
    return paginate_query(query, lambda plan: plan.to_dict())


@bp.post("/plans")
def create_plan():
    payload = inspection_service.validate_plan_payload(json_payload())
    plan = inspection_service.create_plan(payload)
    return plan.to_dict(), 201


@bp.put("/plans/<int:plan_id>")
def update_plan(plan_id):
    plan = inspection_service.get_plan(plan_id)
    payload = inspection_service.validate_plan_payload(json_payload(), partial=True)
    return inspection_service.update_plan(plan, payload).to_dict()


@bp.delete("/plans/<int:plan_id>")
def delete_plan(plan_id):
    plan = inspection_service.get_plan(plan_id)
    inspection_service.delete_plan(plan)
    return {"id": plan_id, "removed": True}


@bp.post("/plans/<int:plan_id>/dispatch")
def dispatch_plan(plan_id):
    """派发单个计划的本期任务; 同周期重复派发返回已有任务."""
    plan = inspection_service.get_plan(plan_id)
    task, created = inspection_service.dispatch_plan(plan)
    payload = task.to_dict()
    payload["created"] = created
    return payload, 201 if created else 200


@bp.post("/dispatch")
def dispatch_all():
    """一键派发: 所有启用中的计划生成本期巡检任务."""
    return inspection_service.dispatch_all()


# ---- 巡检任务 -------------------------------------------------------------
@bp.get("/tasks")
def list_tasks():
    query = inspection_service.task_query(request.args)
    return paginate_query(query, lambda task: task.to_dict())


@bp.post("/tasks")
def create_task():
    """手工临时派发巡检任务."""
    task = inspection_service.create_adhoc_task(json_payload())
    return task.to_dict(), 201


@bp.get("/tasks/<int:task_id>")
def get_task(task_id):
    task = inspection_service.get_task(task_id)
    return task.to_dict(include_items=True, include_repairs=True)


@bp.post("/tasks/<int:task_id>/start")
def start_task(task_id):
    task = inspection_service.get_task(task_id)
    data = json_payload() if request.data else {}
    executor = (data.get("executor") or "").strip() or None
    return inspection_service.start_task(task, executor=executor).to_dict()


@bp.post("/tasks/<int:task_id>/complete")
def complete_task(task_id):
    """提交巡检结果; 存在异常项时可携带 repair 对象同事务生成维修工单."""
    task = inspection_service.get_task(task_id)
    data = json_payload()
    validator = Validator(data)
    executor = validator.text("executor", "巡检人", required=False, max_length=64)
    summary = validator.text("summary", "巡检总结", required=False, max_length=1000)
    validator.raise_if_invalid("巡检结果不合法")

    repair_data = data.get("repair")
    if repair_data is not None and not isinstance(repair_data, dict):
        repair_data = None
    task, repair = inspection_service.complete_task(
        task,
        items=data.get("items"),
        executor=executor,
        summary=summary,
        repair_data=repair_data,
    )
    payload = task.to_dict(include_items=True, include_repairs=True)
    payload["repair_order"] = repair.to_dict() if repair else None
    return payload


@bp.post("/tasks/<int:task_id>/cancel")
def cancel_task(task_id):
    task = inspection_service.get_task(task_id)
    data = json_payload() if request.data else {}
    reason = (data.get("reason") or "").strip() or None
    return inspection_service.cancel_task(task, reason=reason).to_dict()
