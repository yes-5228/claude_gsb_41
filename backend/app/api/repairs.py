"""维修工单 API: 报修 / 接单 / 处理完成回写台账."""
from flask import Blueprint, request

from ..domain.constants import REPAIR_PRIORITY_LABELS, REPAIR_STATUS_LABELS, STATION_STATUS_LABELS
from ..errors import ValidationError
from ..extensions import db
from ..models import Station
from ..services import repair_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator
from .helpers import json_payload

bp = Blueprint("repairs", __name__)


@bp.get("/options")
def repair_options():
    return {
        "priorities": [
            {"value": key, "label": label} for key, label in REPAIR_PRIORITY_LABELS.items()
        ],
        "statuses": [
            {"value": key, "label": label} for key, label in REPAIR_STATUS_LABELS.items()
        ],
        "station_statuses": [
            {"value": key, "label": label} for key, label in STATION_STATUS_LABELS.items()
        ],
    }


@bp.get("/summary")
def repair_summary():
    return repair_service.summary(request.args)


@bp.get("/", strict_slashes=False)
def list_repairs():
    query = repair_service.repair_query(request.args)
    return paginate_query(query, lambda repair: repair.to_dict())


@bp.post("/", strict_slashes=False)
def create_repair():
    """手工报修: 不经过巡检任务直接创工单."""
    data = json_payload()
    validator = Validator(data)
    title = validator.text("title", "工单标题", required=True, max_length=160)
    validator.text("description", "问题描述", required=False, max_length=2000)
    validator.choice(
        "priority", "优先级", choices=tuple(REPAIR_PRIORITY_LABELS.keys()),
        required=False, default="medium",
    )
    validator.text("reporter", "报修人", required=False, max_length=64)
    validator.text("handler", "处理人", required=False, max_length=64)
    cleaned = validator.raise_if_invalid("维修工单不合法")

    try:
        station_id = int(data.get("station_id"))
    except (TypeError, ValueError):
        raise ValidationError("请选择监测点", fields={"station_id": "required"})
    station = db.session.get(Station, station_id)
    if station is None:
        raise ValidationError("监测点不存在: id=%s" % station_id, fields={"station_id": "not_found"})

    repair = repair_service.create_repair(station, {**cleaned, "title": title})
    return repair.to_dict(), 201


@bp.get("/<int:repair_id>")
def get_repair(repair_id):
    return repair_service.get_repair(repair_id).to_dict()


@bp.post("/<int:repair_id>/claim")
def claim_repair(repair_id):
    repair = repair_service.get_repair(repair_id)
    data = json_payload() if request.data else {}
    handler = (data.get("handler") or "").strip() or None
    return repair_service.claim_repair(repair, handler=handler).to_dict()


@bp.post("/<int:repair_id>/resolve")
def resolve_repair(repair_id):
    """处理完成: 填写处理结果并回写台账运行状态."""
    repair = repair_service.get_repair(repair_id)
    data = json_payload()
    validator = Validator(data)
    resolution = validator.text("resolution", "处理结果", required=True, max_length=2000)
    handler = validator.text("handler", "处理人", required=False, max_length=64)
    station_status_after = validator.choice(
        "station_status_after", "台账运行状态",
        choices=tuple(STATION_STATUS_LABELS.keys()), required=False, default="active",
    )
    validator.raise_if_invalid("处理结果不合法")
    return repair_service.resolve_repair(
        repair,
        resolution=resolution,
        handler=handler,
        station_status_after=station_status_after or "active",
    ).to_dict()


@bp.post("/<int:repair_id>/close")
def close_repair(repair_id):
    repair = repair_service.get_repair(repair_id)
    data = json_payload() if request.data else {}
    resolution = (data.get("resolution") or "").strip() or None
    station_status_after = (data.get("station_status_after") or "").strip() or None
    return repair_service.close_repair(
        repair, resolution=resolution, station_status_after=station_status_after
    ).to_dict()
