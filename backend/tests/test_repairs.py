"""维修工单接口测试: 报修 / 接单 / 处理回写台账."""
from app.extensions import db
from app.models import RepairOrder, Station


def _create_repair(client, station_id, **overrides):
    payload = {
        "station_id": station_id,
        "title": "分析仪故障",
        "description": "SO2 分析仪无响应",
        "priority": "high",
        "reporter": "李静",
    }
    payload.update(overrides)
    return client.post("/api/repairs/", json=payload)


def test_create_repair_sets_station_maintenance(client, station):
    response = _create_repair(client, station.id)
    assert response.status_code == 201
    body = response.get_json()
    assert body["code"].startswith("WX")
    assert body["status"] == "open"
    assert body["priority_label"] == "高"
    assert body["station_status_before"] == "active"

    # 设备异常期间台账置为维护中
    assert db.session.get(Station, station.id).status == "maintenance"


def test_create_repair_validation(client, station):
    missing_title = client.post("/api/repairs/", json={"station_id": station.id})
    assert missing_title.status_code == 422
    assert "title" in missing_title.get_json()["error"]["fields"]

    bad_station = _create_repair(client, 9999)
    assert bad_station.status_code == 422

    bad_priority = _create_repair(client, station.id, priority="critical")
    assert bad_priority.status_code == 422


def test_repair_with_handler_starts_processing(client, station):
    body = _create_repair(client, station.id, handler="赵宇").get_json()
    assert body["status"] == "processing"


def test_claim_then_resolve_flow(client, station):
    repair_id = _create_repair(client, station.id).get_json()["id"]

    claimed = client.post("/api/repairs/%d/claim" % repair_id, json={"handler": "赵宇"})
    assert claimed.get_json()["status"] == "processing"

    resolved = client.post(
        "/api/repairs/%d/resolve" % repair_id,
        json={"resolution": "已更换主板并恢复运行", "station_status_after": "active"},
    )
    assert resolved.status_code == 200
    body = resolved.get_json()
    assert body["status"] == "resolved"
    assert body["handler"] == "赵宇"
    assert db.session.get(Station, station.id).status == "active"

    # 已修复工单不能重复处理
    again = client.post(
        "/api/repairs/%d/resolve" % repair_id, json={"resolution": "重复处理"}
    )
    assert again.status_code == 422


def test_resolve_requires_resolution_and_valid_status(client, station):
    repair_id = _create_repair(client, station.id).get_json()["id"]

    empty = client.post("/api/repairs/%d/resolve" % repair_id, json={"resolution": ""})
    assert empty.status_code == 422
    assert "resolution" in empty.get_json()["error"]["fields"]

    bad_status = client.post(
        "/api/repairs/%d/resolve" % repair_id,
        json={"resolution": "已处理", "station_status_after": "running"},
    )
    assert bad_status.status_code == 422
    assert "station_status_after" in bad_status.get_json()["error"]["fields"]


def test_resolve_can_keep_station_in_maintenance(client, station):
    repair_id = _create_repair(client, station.id).get_json()["id"]
    resolved = client.post(
        "/api/repairs/%d/resolve" % repair_id,
        json={
            "resolution": "临时修复, 待备件到货后复检",
            "handler": "赵宇",
            "station_status_after": "maintenance",
        },
    )
    assert resolved.status_code == 200
    assert db.session.get(Station, station.id).status == "maintenance"


def test_close_repair_with_optional_writeback(client, station):
    repair_id = _create_repair(client, station.id).get_json()["id"]
    assert db.session.get(Station, station.id).status == "maintenance"

    closed = client.post(
        "/api/repairs/%d/close" % repair_id,
        json={"resolution": "现场复核为误报", "station_status_after": "active"},
    )
    assert closed.status_code == 200
    body = closed.get_json()
    assert body["status"] == "closed"
    assert body["closed_at"]
    assert db.session.get(Station, station.id).status == "active"


def test_repair_list_filters_and_summary(client, station, second_station):
    _create_repair(client, station.id, title="工单A", priority="urgent")
    _create_repair(client, second_station.id, title="工单B", priority="low", handler="赵宇")

    urgent = client.get("/api/repairs/?priority=urgent").get_json()
    assert urgent["total"] == 1
    assert urgent["items"][0]["title"] == "工单A"

    processing = client.get("/api/repairs/?status=processing").get_json()
    assert processing["total"] == 1

    keyword = client.get("/api/repairs/?keyword=工单B").get_json()
    assert keyword["total"] == 1

    summary = client.get("/api/repairs/summary").get_json()
    assert summary["total"] == 2
    assert summary["open"] == 2
    assert summary["urgent_open"] == 1


def test_missing_repair_returns_404(client):
    assert client.get("/api/repairs/999").status_code == 404
    assert client.post("/api/repairs/999/claim", json={}).status_code == 404
