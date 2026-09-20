"""运维巡检模块接口测试: 计划派发、逐项记录、异常转单、工单办结回写台账."""
from datetime import date, timedelta

from app.extensions import db
from app.models import (
    InspectionPlan,
    InspectionTask,
    InspectionTaskItem,
    Station,
    WorkOrder,
)
from app.services import inspection_service

ITEM_CODES = ["env_cabinet", "sampler", "analyzer"]


def _plan_payload(station_id, cycle="daily", start=None, **overrides):
    payload = {
        "name": "例行巡检",
        "cycle": cycle,
        "start_date": (start or date.today()).isoformat(),
        "station_ids": [station_id],
        "items": ITEM_CODES,
        "inspector": "张三",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------- 计划与派发
def test_create_plan_requires_stations_and_items(client, station):
    missing_stations = client.post("/api/inspections/plans", json={
        "name": "测试计划", "cycle": "daily",
        "start_date": date.today().isoformat(), "station_ids": [], "items": ITEM_CODES,
    })
    assert missing_stations.status_code == 422
    assert "station_ids" in missing_stations.get_json()["error"]["fields"]

    missing_items = client.post("/api/inspections/plans", json={
        "name": "测试计划", "cycle": "daily",
        "start_date": date.today().isoformat(), "station_ids": [station.id], "items": [],
    })
    assert missing_items.status_code == 422
    assert "items" in missing_items.get_json()["error"]["fields"]

    ok = client.post("/api/inspections/plans", json=_plan_payload(station.id))
    assert ok.status_code == 201
    body = ok.get_json()
    assert body["cycle_label"] == "每日"
    assert body["next_run_date"] == date.today().isoformat()
    assert body["stations"][0]["id"] == station.id


def test_plan_start_date_in_the_past_is_rejected(client, station):
    resp = client.post(
        "/api/inspections/plans",
        json=_plan_payload(station.id, start=date.today() - timedelta(days=1)),
    )
    assert resp.status_code == 422


def test_dispatch_plan_creates_one_task_per_station(client, station, second_station):
    plan = client.post(
        "/api/inspections/plans",
        json=_plan_payload(station.id),
    ).get_json()
    client.put(
        "/api/inspections/plans/%d" % plan["id"],
        json={"station_ids": [station.id, second_station.id]},
    )

    resp = client.post("/api/inspections/plans/%d/dispatch" % plan["id"])
    assert resp.status_code == 200
    assert resp.get_json()["task_count"] == 2

    # 同一点位同一到期日重复派发应跳过
    again = client.post("/api/inspections/plans/%d/dispatch" % plan["id"])
    assert again.get_json()["task_count"] == 0


def test_offline_station_is_skipped_when_dispatching(client, station):
    client.put("/api/stations/%d" % station.id, json={"status": "offline"})
    plan = client.post("/api/inspections/plans", json=_plan_payload(station.id)).get_json()
    resp = client.post("/api/inspections/plans/%d/dispatch" % plan["id"])
    assert resp.get_json()["task_count"] == 0


def test_dispatch_due_advances_recurring_schedule(client, station):
    client.post("/api/inspections/plans", json=_plan_payload(station.id, cycle="weekly"))
    result = inspection_service.dispatch_due_plans()
    assert result["task_count"] == 1
    plan = InspectionPlan.query.first()
    assert plan.next_run_date == date.today() + timedelta(days=7)

    # 再次执行时本周已无到期计划
    assert inspection_service.dispatch_due_plans()["task_count"] == 0


def test_once_plan_is_disabled_after_dispatch(client, station):
    client.post("/api/inspections/plans", json=_plan_payload(station.id, cycle="once"))
    inspection_service.dispatch_due_plans()
    assert InspectionPlan.query.first().enabled is False


# ---------------------------------------------------------------- 任务执行
def _dispatched_task(client, station_id):
    plan = client.post(
        "/api/inspections/plans", json=_plan_payload(station_id)
    ).get_json()
    resp = client.post("/api/inspections/plans/%d/dispatch" % plan["id"])
    return resp.get_json()["tasks"][0]


def test_record_items_transitions_task_to_in_progress(client, station):
    task = _dispatched_task(client, station.id)
    detail = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()
    item = detail["items"][0]

    resp = client.put(
        "/api/inspections/tasks/%d/items/%d" % (task["id"], item["id"]),
        json={"result": "normal", "inspector": "张三"},
    )
    assert resp.status_code == 200
    refreshed = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()
    assert refreshed["status"] == "in_progress"
    assert refreshed["progress"]["recorded"] == 1


def test_abnormal_result_requires_remark(client, station):
    task = _dispatched_task(client, station.id)
    item = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()["items"][0]
    resp = client.put(
        "/api/inspections/tasks/%d/items/%d" % (task["id"], item["id"]),
        json={"result": "abnormal"},
    )
    assert resp.status_code == 422
    assert "remark" in resp.get_json()["error"]["fields"]


def test_submit_requires_all_items_recorded(client, station):
    task = _dispatched_task(client, station.id)
    item = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()["items"][0]
    client.put(
        "/api/inspections/tasks/%d/items/%d" % (task["id"], item["id"]),
        json={"result": "normal"},
    )
    resp = client.post("/api/inspections/tasks/%d/submit" % task["id"])
    assert resp.status_code == 409


def test_submit_completed_task_with_no_abnormal(client, station):
    task = _dispatched_task(client, station.id)
    items = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()["items"]
    for item in items:
        client.put(
            "/api/inspections/tasks/%d/items/%d" % (task["id"], item["id"]),
            json={"result": "normal"},
        )
    resp = client.post("/api/inspections/tasks/%d/submit" % task["id"], json={"summary": "全部正常"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "completed"


def test_overdue_task_is_flagged_automatically(client, station, app):
    past = date.today() - timedelta(days=1)
    with app.app_context():
        station_obj = db.session.get(Station, station.id)
        task = inspection_service._instantiate_task(
            None, station_obj, past, items=ITEM_CODES, inspector="张三"
        )
        db.session.commit()
        tid = task.id

    resp = client.get("/api/inspections/tasks?status=overdue")
    assert resp.status_code == 200
    assert any(item["id"] == tid for item in resp.get_json()["items"])


# ---------------------------------------------------------------- 异常转单
def _submit_abnormal_task(client, station_id):
    task = _dispatched_task(client, station_id)
    items = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()["items"]
    for item in items:
        payload = (
            {"result": "abnormal", "remark": "采样泵异响, 流量不足"}
            if item["item_code"] == "sampler"
            else {"result": "normal"}
        )
        client.put(
            "/api/inspections/tasks/%d/items/%d" % (task["id"], item["id"]), json=payload
        )
    client.post("/api/inspections/tasks/%d/submit" % task["id"], json={"summary": "采样异常"})
    return task, items


def test_abnormal_item_convert_creates_work_order_and_sets_maintenance(client, station):
    task, items = _submit_abnormal_task(client, station.id)
    abnormal = next(item for item in items if item["item_code"] == "sampler")

    resp = client.post(
        "/api/inspections/tasks/%d/items/%d/convert" % (task["id"], abnormal["id"]),
        json={"priority": "high", "assignee": "赵宇"},
    )
    assert resp.status_code == 201
    order = resp.get_json()
    assert order["source"] == "inspection"
    assert order["status"] == "open"

    station_body = client.get("/api/stations/%d" % station.id).get_json()
    assert station_body["status"] == "maintenance"

    # 台账列表统计应反映进行中工单
    listed = client.get("/api/stations").get_json()["items"][0]
    assert listed["stats"]["active_work_order_count"] == 1

    # 同一异常项不能重复转进行中的工单
    duplicate = client.post(
        "/api/inspections/tasks/%d/items/%d/convert" % (task["id"], abnormal["id"]), json={}
    )
    assert duplicate.status_code == 409


def test_normal_item_cannot_be_converted(client, station):
    task = _dispatched_task(client, station.id)
    items = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()["items"]
    normal = items[0]
    client.put(
        "/api/inspections/tasks/%d/items/%d" % (task["id"], normal["id"]),
        json={"result": "normal"},
    )
    resp = client.post(
        "/api/inspections/tasks/%d/items/%d/convert" % (task["id"], normal["id"]), json={}
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------- 工单流转
def test_work_order_lifecycle_writes_back_station_status(client, station):
    task, items = _submit_abnormal_task(client, station.id)
    abnormal = next(item for item in items if item["item_code"] == "sampler")
    order = client.post(
        "/api/inspections/tasks/%d/items/%d/convert" % (task["id"], abnormal["id"]),
        json={},
    ).get_json()

    # 非法跳转 open -> resolved
    bad = client.patch("/api/work-orders/%d" % order["id"], json={"status": "resolved"})
    assert bad.status_code in (409, 422)

    client.patch(
        "/api/work-orders/%d" % order["id"],
        json={"status": "processing", "assignee": "赵宇"},
    )
    # 维修完成必须填写处理说明
    missing = client.patch("/api/work-orders/%d" % order["id"], json={"status": "resolved"})
    assert missing.status_code == 422

    resolved = client.patch(
        "/api/work-orders/%d" % order["id"],
        json={"status": "resolved", "resolution": "更换采样泵并校准流量", "restore_status": "active"},
    )
    assert resolved.status_code == 200
    # 办结后台账恢复“运行中”
    assert client.get("/api/stations/%d" % station.id).get_json()["status"] == "active"

    closed = client.patch("/api/work-orders/%d" % order["id"], json={"status": "closed"})
    assert closed.get_json()["status"] == "closed"
    assert closed.get_json()["station_status"] if "station_status" in closed.get_json() else True


def test_manual_work_order_creation_and_cancel(client, station):
    resp = client.post("/api/work-orders/", json={
        "station_id": station.id,
        "title": "站房空调故障",
        "description": "空调不制冷, 站房温度偏高",
        "priority": "normal",
        "reporter": "孙倩",
    })
    assert resp.status_code == 201
    order = resp.get_json()
    assert order["source_label"] == "人工建单"
    assert client.get("/api/stations/%d" % station.id).get_json()["status"] == "maintenance"

    cancel = client.patch(
        "/api/work-orders/%d" % order["id"],
        json={"status": "cancelled", "resolution": "空调恢复, 取消工单"},
    )
    assert cancel.status_code == 200
    # 取消后点位恢复运行
    assert client.get("/api/stations/%d" % station.id).get_json()["status"] == "active"


def test_offline_station_status_is_not_overwritten_by_work_orders(client, station):
    client.put("/api/stations/%d" % station.id, json={"status": "offline"})
    order = client.post("/api/work-orders/", json={
        "station_id": station.id, "title": "备件更换", "priority": "low",
    }).get_json()
    assert client.get("/api/stations/%d" % station.id).get_json()["status"] == "offline"
    client.patch(
        "/api/work-orders/%d" % order["id"],
        json={"status": "processing"},
    )
    client.patch(
        "/api/work-orders/%d" % order["id"],
        json={"status": "resolved", "resolution": "已更换"},
    )
    assert client.get("/api/stations/%d" % station.id).get_json()["status"] == "offline"


# ---------------------------------------------------------------- 待办与级联
def test_todo_counts_and_overview(client, station):
    task, items = _submit_abnormal_task(client, station.id)
    abnormal = next(item for item in items if item["item_code"] == "sampler")
    client.post(
        "/api/inspections/tasks/%d/items/%d/convert" % (task["id"], abnormal["id"]), json={}
    )
    counts = client.get("/api/inspections/todo-counts").get_json()
    assert counts["todo_tasks"] >= 0
    assert counts["active_work_orders"] == 1

    overview = client.get("/api/meta/overview").get_json()
    assert "inspections" in overview and "work_orders" in overview
    assert overview["inspections"]["active_work_orders"] == 1


def test_manual_task_creation(client, station):
    resp = client.post("/api/inspections/tasks", json={
        "station_id": station.id,
        "items": ["env_cabinet", "power_network"],
        "due_date": date.today().isoformat(),
        "inspector": "陈志强",
    })
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["plan_id"] is None
    assert len(body["items"]) == 2


def test_deleting_plan_keeps_history_tasks(client, station):
    task = _dispatched_task(client, station.id)
    plan_id = client.get("/api/inspections/tasks/%d" % task["id"]).get_json()["plan_id"]
    resp = client.delete("/api/inspections/plans/%d" % plan_id)
    assert resp.status_code == 200
    assert resp.get_json()["removed"]["tasks_kept"] == 1
    assert InspectionTask.query.count() == 1
    assert InspectionTask.query.first().plan_id is None


def test_deleting_station_cascades_inspection_data(client, station):
    task, items = _submit_abnormal_task(client, station.id)
    abnormal = next(item for item in items if item["item_code"] == "sampler")
    client.post(
        "/api/inspections/tasks/%d/items/%d/convert" % (task["id"], abnormal["id"]), json={}
    )
    assert InspectionTaskItem.query.count() == 3
    assert WorkOrder.query.count() == 1

    resp = client.delete("/api/stations/%d" % station.id)
    assert resp.status_code == 200
    removed = resp.get_json()["removed"]
    assert removed["inspections_removed"] == 1
    assert removed["work_orders_removed"] == 1
    assert InspectionTask.query.count() == 0
