"""运维巡检模块接口测试: 计划 / 派发 / 执行 / 转工单 / 状态一致性."""
from app.extensions import db
from app.models import InspectionPlan, InspectionTask, RepairOrder, Station


def _create_plan(client, station_id, **overrides):
    payload = {
        "station_id": station_id,
        "name": "测试巡检计划",
        "cycle": "monthly",
        "items": ["采样管路", "分析仪状态", "供电系统"],
        "assignee": "李静",
    }
    payload.update(overrides)
    return client.post("/api/inspections/plans", json=payload)


def test_create_plan_and_options(client, station):
    response = _create_plan(client, station.id)
    assert response.status_code == 201
    body = response.get_json()
    assert body["cycle_label"] == "每月"
    assert body["items"] == ["采样管路", "分析仪状态", "供电系统"]
    assert body["station_name"] == "测试监测点"

    options = client.get("/api/inspections/options").get_json()
    assert len(options["item_catalog"]) >= 5
    assert {item["value"] for item in options["cycles"]} == {"weekly", "monthly", "quarterly"}


def test_plan_validation_errors(client, station):
    missing_items = _create_plan(client, station.id, items=[])
    assert missing_items.status_code == 422
    assert "items" in missing_items.get_json()["error"]["fields"]

    bad_station = _create_plan(client, 9999)
    assert bad_station.status_code == 422
    assert "station_id" in bad_station.get_json()["error"]["fields"]

    bad_cycle = _create_plan(client, station.id, cycle="yearly")
    assert bad_cycle.status_code == 422
    assert "cycle" in bad_cycle.get_json()["error"]["fields"]


def test_dispatch_is_idempotent_per_period(client, station):
    plan_id = _create_plan(client, station.id).get_json()["id"]

    first = client.post("/api/inspections/plans/%d/dispatch" % plan_id)
    assert first.status_code == 201
    task = first.get_json()
    assert task["created"] is True
    assert task["status"] == "pending"
    assert task["period_key"]
    assert task["item_total"] == 3

    again = client.post("/api/inspections/plans/%d/dispatch" % plan_id)
    assert again.status_code == 200
    assert again.get_json()["created"] is False
    assert again.get_json()["id"] == task["id"]
    assert InspectionTask.query.count() == 1


def test_dispatch_all_covers_active_plans_only(client, station, second_station):
    _create_plan(client, station.id, name="计划A")
    _create_plan(client, second_station.id, name="计划B", cycle="weekly")
    inactive = _create_plan(client, second_station.id, name="计划C", active=False).get_json()

    # 停用的计划不参与一键派发
    client.put("/api/inspections/plans/%d" % inactive["id"], json={"active": False})
    result = client.post("/api/inspections/dispatch").get_json()
    assert result["created_count"] == 2

    # 重复派发全部跳过
    again = client.post("/api/inspections/dispatch").get_json()
    assert again["created_count"] == 0
    assert again["skipped_count"] == 2


def test_delete_plan_with_tasks_is_rejected(client, station):
    plan_id = _create_plan(client, station.id).get_json()["id"]
    client.post("/api/inspections/plans/%d/dispatch" % plan_id)
    response = client.delete("/api/inspections/plans/%d" % plan_id)
    assert response.status_code == 409


def test_adhoc_task_creation(client, station):
    response = client.post(
        "/api/inspections/tasks",
        json={"station_id": station.id, "items": ["临时检查项"], "assignee": "王敏"},
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["plan_id"] is None
    assert "临时巡检" in body["title"]

    missing = client.post("/api/inspections/tasks", json={"station_id": station.id, "items": []})
    assert missing.status_code == 422


def _dispatch_and_get_task(client, station):
    plan_id = _create_plan(client, station.id).get_json()["id"]
    client.post("/api/inspections/plans/%d/dispatch" % plan_id)
    task = InspectionTask.query.first()
    detail = client.get("/api/inspections/tasks/%d" % task.id).get_json()
    return task.id, detail


def test_task_lifecycle_normal_completion(client, station):
    task_id, detail = _dispatch_and_get_task(client, station)
    assert detail["status"] == "pending"
    assert all(item["result"] == "pending" for item in detail["items"])

    started = client.post("/api/inspections/tasks/%d/start" % task_id, json={"executor": "李静"})
    assert started.get_json()["status"] == "in_progress"

    items = [
        {"id": item["id"], "result": "normal", "note": ""} for item in detail["items"]
    ]
    done = client.post(
        "/api/inspections/tasks/%d/complete" % task_id,
        json={"items": items, "executor": "李静", "summary": "一切正常"},
    )
    assert done.status_code == 200
    body = done.get_json()
    assert body["status"] == "completed"
    assert body["result"] == "normal"
    assert body["repair_order"] is None
    assert all(item["result"] == "normal" for item in body["items"])

    # 台账状态未被巡检影响
    assert db.session.get(Station, station.id).status == "active"


def test_complete_requires_all_items_and_abnormal_note(client, station):
    task_id, detail = _dispatch_and_get_task(client, station)

    partial = client.post(
        "/api/inspections/tasks/%d/complete" % task_id,
        json={"items": [{"id": detail["items"][0]["id"], "result": "normal"}]},
    )
    assert partial.status_code == 422

    no_note = client.post(
        "/api/inspections/tasks/%d/complete" % task_id,
        json={
            "items": [
                {"id": item["id"], "result": "abnormal", "note": ""}
                for item in detail["items"]
            ],
            "executor": "李静",
        },
    )
    assert no_note.status_code == 422
    assert "异常说明" in no_note.get_json()["error"]["message"]


def test_abnormal_completion_creates_repair_and_updates_station(client, station):
    task_id, detail = _dispatch_and_get_task(client, station)
    items = []
    for index, item in enumerate(detail["items"]):
        if index == 0:
            items.append({"id": item["id"], "result": "abnormal", "note": "采样管路漏气"})
        else:
            items.append({"id": item["id"], "result": "normal", "note": ""})

    done = client.post(
        "/api/inspections/tasks/%d/complete" % task_id,
        json={
            "items": items,
            "executor": "李静",
            "summary": "发现设备异常",
            "repair": {"priority": "high"},
        },
    )
    assert done.status_code == 200
    body = done.get_json()
    assert body["result"] == "abnormal"
    assert body["abnormal_count"] == 1

    repair = body["repair_order"]
    assert repair is not None
    assert repair["status"] == "open"
    assert repair["priority"] == "high"
    assert repair["inspection_task_id"] == task_id
    assert "采样管路" in repair["description"]
    assert repair["station_status_before"] == "active"

    # 台账状态已切换为维护中, 待办列表出现该工单
    assert db.session.get(Station, station.id).status == "maintenance"
    todo = client.get("/api/inspections/todo").get_json()
    assert todo["repair_count"] == 1
    assert todo["repairs"][0]["id"] == repair["id"]
    assert todo["task_count"] == 0  # 任务已完成, 不再出现在待办


def test_repair_resolve_writes_back_station_status(client, station):
    task_id, detail = _dispatch_and_get_task(client, station)
    items = [
        {"id": detail["items"][0]["id"], "result": "abnormal", "note": "UPS 无法续航"},
    ] + [
        {"id": item["id"], "result": "normal", "note": ""} for item in detail["items"][1:]
    ]
    done = client.post(
        "/api/inspections/tasks/%d/complete" % task_id,
        json={"items": items, "executor": "李静", "repair": {"priority": "urgent"}},
    ).get_json()
    repair_id = done["repair_order"]["id"]
    assert db.session.get(Station, station.id).status == "maintenance"

    resolved = client.post(
        "/api/repairs/%d/resolve" % repair_id,
        json={
            "resolution": "已更换 UPS 电池组并恢复供电",
            "handler": "赵宇",
            "station_status_after": "active",
        },
    )
    assert resolved.status_code == 200
    body = resolved.get_json()
    assert body["status"] == "resolved"
    assert body["station_status_after"] == "active"
    assert body["resolved_at"]

    # 台账回写运行中, 待办清空 —— 台账 / 巡检 / 待办状态一致
    assert db.session.get(Station, station.id).status == "active"
    todo = client.get("/api/inspections/todo").get_json()
    assert todo["repair_count"] == 0
    assert todo["task_count"] == 0


def test_cancel_task(client, station):
    task_id, _ = _dispatch_and_get_task(client, station)
    cancelled = client.post(
        "/api/inspections/tasks/%d/cancel" % task_id, json={"reason": "站点搬迁"}
    )
    assert cancelled.get_json()["status"] == "cancelled"

    again = client.post("/api/inspections/tasks/%d/start" % task_id, json={})
    assert again.status_code == 422


def test_task_list_filters_and_summary(client, station, second_station):
    _create_plan(client, station.id, name="计划A", cycle="weekly")
    _create_plan(client, second_station.id, name="计划B", cycle="monthly")
    client.post("/api/inspections/dispatch")

    weekly = client.get("/api/inspections/tasks?cycle=weekly").get_json()
    assert weekly["total"] == 1
    assert weekly["items"][0]["station_id"] == station.id

    by_station = client.get("/api/inspections/tasks?station_id=%d" % second_station.id).get_json()
    assert by_station["total"] == 1

    summary = client.get("/api/inspections/summary").get_json()
    assert summary["plan_total"] == 2
    assert summary["task_open"] == 2
    assert summary["repair"]["open"] == 0


def test_station_stats_include_inspection_counters(client, station):
    _create_plan(client, station.id)
    client.post("/api/inspections/dispatch")
    detail = client.get("/api/stations/%d" % station.id).get_json()
    assert detail["stats"]["open_task_count"] == 1
    assert detail["stats"]["open_repair_count"] == 0


def test_delete_station_cascades_inspection_data(client, station):
    plan_id = _create_plan(client, station.id).get_json()["id"]
    client.post("/api/inspections/plans/%d/dispatch" % plan_id)
    task = InspectionTask.query.first()
    detail = client.get("/api/inspections/tasks/%d" % task.id).get_json()
    client.post(
        "/api/inspections/tasks/%d/complete" % task.id,
        json={
            "items": [
                {"id": item["id"], "result": "abnormal", "note": "异常"}
                if index == 0
                else {"id": item["id"], "result": "normal", "note": ""}
                for index, item in enumerate(detail["items"])
            ],
            "executor": "李静",
            "repair": {"priority": "medium"},
        },
    )
    assert RepairOrder.query.count() == 1

    removed = client.delete("/api/stations/%d" % station.id).get_json()["removed"]
    assert removed["inspection_tasks_removed"] == 1
    assert removed["repair_orders_removed"] == 1
    assert InspectionPlan.query.count() == 0
    assert InspectionTask.query.count() == 0
    assert RepairOrder.query.count() == 0
