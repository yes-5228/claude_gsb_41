"""维修工单 API: 建单、派单、维修办结与台账状态回写."""
from flask import Blueprint, request

from ..domain.constants import (
    STATION_STATUS_LABELS,
    WORK_ORDER_PRIORITY_LABELS,
    WORK_ORDER_SOURCE_LABELS,
    WORK_ORDER_STATUS_LABELS,
)
from ..services import station_service, work_order_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator
from .helpers import json_payload

bp = Blueprint("work_orders", __name__)


@bp.get("/", strict_slashes=False)
def list_orders():
    query = work_order_service.work_order_query(request.args)
    result = paginate_query(query, lambda row: row.to_dict())
    result["summary"] = work_order_service.summary(request.args)
    result["areas"] = station_service.area_list()
    return result


@bp.get("/summary")
def orders_summary():
    return work_order_service.summary(request.args)


@bp.get("/options")
def order_options():
    return {
        "statuses": [{"value": k, "label": v} for k, v in WORK_ORDER_STATUS_LABELS.items()],
        "priorities": [{"value": k, "label": v} for k, v in WORK_ORDER_PRIORITY_LABELS.items()],
        "sources": [{"value": k, "label": v} for k, v in WORK_ORDER_SOURCE_LABELS.items()],
        "station_status": [{"value": k, "label": v} for k, v in STATION_STATUS_LABELS.items()],
    }


@bp.post("/", strict_slashes=False)
def create_order():
    """人工建单 (非巡检转单)."""
    data = json_payload()
    validator = Validator(data)
    station_id = validator.number("station_id", "监测点", required=True, minimum=1)
    title = validator.text("title", "工单标题", required=True, max_length=160)
    description = validator.text("description", "故障描述", required=False, max_length=1000)
    priority = validator.choice(
        "priority", "优先级",
        choices=tuple(WORK_ORDER_PRIORITY_LABELS.keys()), required=False, default="normal",
    )
    reporter = validator.text("reporter", "报修人", required=False, max_length=64)
    assignee = validator.text("assignee", "维修负责人", required=False, max_length=64)
    validator.date_field("due_date", "要求完成日期")
    validator.raise_if_invalid("工单信息不合法")

    order = work_order_service.create_work_order(
        station_id=int(station_id),
        title=title,
        description=description,
        priority=priority or "normal",
        reporter=reporter,
        assignee=assignee,
        source="manual",
        due_date=validator.cleaned.get("due_date"),
    )
    return order.to_dict(), 201


@bp.get("/<int:order_id>")
def get_order(order_id):
    return work_order_service.get_work_order(order_id).to_dict()


@bp.patch("/<int:order_id>")
def update_order(order_id):
    """工单状态流转: 派单/开始维修/维修完成/关闭/取消, 并回写台账状态."""
    order = work_order_service.get_work_order(order_id)
    data = json_payload()
    validator = Validator(data)
    status = validator.choice(
        "status", "工单状态", choices=tuple(WORK_ORDER_STATUS_LABELS.keys()), required=False
    )
    assignee = validator.text("assignee", "维修负责人", required=False, max_length=64)
    resolution = validator.text("resolution", "处理说明", required=False, max_length=1000)
    restore_status = validator.choice(
        "restore_status", "恢复台账状态",
        choices=tuple(STATION_STATUS_LABELS.keys()), required=False,
    )
    validator.raise_if_invalid("工单更新不合法")

    if status is None:
        if assignee is not None:
            order = work_order_service.assign(order, assignee)
        return order.to_dict()
    order = work_order_service.transition(
        order,
        target=status,
        assignee=assignee,
        resolution=resolution,
        restore_status=restore_status,
    )
    return order.to_dict()
