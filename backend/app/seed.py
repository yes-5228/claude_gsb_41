"""演示数据生成与启动引导."""
import random
from datetime import date, datetime, timedelta

from .extensions import db
from .models import (
    Exceedance,
    InspectionPlan,
    InspectionTask,
    Measurement,
    Station,
    WorkOrder,
)
from .models.inspection_plan import plan_station

DEMO_STATIONS = [
    {
        "code": "SZ-AQ-001", "name": "市民中心站", "area": "福田区",
        "address": "福田区福中三路市民中心广场", "station_type": "ambient",
        "status": "active", "longitude": 114.0579, "latitude": 22.5410,
        "installed_at": date(2019, 5, 12), "remark": "城市环境评价点",
    },
    {
        "code": "SZ-AQ-002", "name": "华侨城站", "area": "南山区",
        "address": "南山区华侨城生态广场", "station_type": "ambient",
        "status": "active", "longitude": 113.9711, "latitude": 22.5356,
        "installed_at": date(2020, 3, 1), "remark": "城市环境评价点",
    },
    {
        "code": "SZ-AQ-003", "name": "罗湖口岸站", "area": "罗湖区",
        "address": "罗湖区火车站东广场", "station_type": "traffic",
        "status": "active", "longitude": 114.1276, "latitude": 22.5329,
        "installed_at": date(2018, 11, 20), "remark": "道路交通监测点, 早晚高峰浓度偏高",
    },
    {
        "code": "SZ-AQ-004", "name": "宝安中心站", "area": "宝安区",
        "address": "宝安区中心区宝安大道", "station_type": "ambient",
        "status": "active", "longitude": 113.8830, "latitude": 22.5551,
        "installed_at": date(2021, 6, 18), "remark": None,
    },
    {
        "code": "SZ-AQ-005", "name": "龙岗工业园站", "area": "龙岗区",
        "address": "龙岗区宝龙工业区龙岗大道", "station_type": "industrial",
        "status": "active", "longitude": 114.2465, "latitude": 22.7204,
        "installed_at": date(2019, 9, 8), "remark": "周边为工业排放源, 需重点关注 SO₂",
    },
    {
        "code": "SZ-AQ-006", "name": "梧桐山背景站", "area": "罗湖区",
        "address": "罗湖区梧桐山风景区", "station_type": "background",
        "status": "active", "longitude": 114.1837, "latitude": 22.5862,
        "installed_at": date(2017, 4, 2), "remark": "区域背景点, 用于对照评价",
    },
    {
        "code": "SZ-AQ-007", "name": "大鹏生态站", "area": "大鹏新区",
        "address": "大鹏新区葵涌街道", "station_type": "rural",
        "status": "maintenance", "longitude": 114.4798, "latitude": 22.5964,
        "installed_at": date(2022, 8, 15), "remark": "设备检修中, 计划本周恢复",
    },
    {
        "code": "SZ-AQ-008", "name": "前海自贸区站", "area": "南山区",
        "address": "南山区前海湾保税港区", "station_type": "ambient",
        "status": "offline", "longitude": 113.8980, "latitude": 22.5253,
        "installed_at": date(2023, 1, 10), "remark": "站点搬迁停用",
    },
]

POLLUTANT_BASE = {"PM25": 45.0, "PM10": 80.0, "SO2": 30.0, "NO2": 45.0, "CO": 1.5, "O3": 120.0}
HOURLY_FACTOR = {"PM25": 1.0, "PM10": 1.05, "SO2": 0.8, "NO2": 1.1, "CO": 0.9, "O3": 1.3}
STATION_FACTOR = {
    "ambient": 1.0, "traffic": 1.2, "industrial": 1.35, "background": 0.55, "rural": 0.75,
}
HOURLY_POINTS = (2, 8, 14, 20)
RECORDERS = ("李静", "王敏", "陈志强", "赵宇", "孙倩")


def _value(pollutant, period, station_type, rng):
    base = POLLUTANT_BASE[pollutant] * STATION_FACTOR.get(station_type, 1.0)
    if period == "hourly":
        base *= HOURLY_FACTOR[pollutant]
    value = base * rng.uniform(0.72, 1.22)
    if rng.random() < 0.12:  # 少量明显超标样本, 便于演示超标标注
        value *= rng.uniform(1.8, 2.6)
    return round(value, 2 if pollutant == "CO" else 1)


def seed_demo_data(days=5, rng=None, recorder_pool=RECORDERS):
    """Generate demo stations and monitoring records through the normal service path."""
    from .services import measurement_service

    rng = rng or random.Random(20260914)
    created_stations = []
    for item in DEMO_STATIONS:
        station = Station(**item)
        db.session.add(station)
        created_stations.append(station)
    db.session.commit()

    today = date.today()
    totals = {"stations": len(created_stations), "measurements": 0, "exceedances": 0}
    for station in created_stations:
        for offset in range(days):
            day = today - timedelta(days=offset)
            daily_entries = [
                {"pollutant": code, "value": _value(code, "daily", station.station_type, rng)}
                for code in POLLUTANT_BASE
            ]
            result = measurement_service.record_entries(
                station_id=station.id,
                measured_at=datetime(day.year, day.month, day.day, 0, 0),
                period="daily",
                entries=daily_entries,
                data_source="device",
                recorder=rng.choice(recorder_pool),
                remark="日均值自动汇总",
            )
            totals["measurements"] += result["summary"]["created_count"]
            totals["exceedances"] += result["summary"]["exceeded_count"]

            for hour in HOURLY_POINTS:
                hourly_entries = [
                    {"pollutant": code, "value": _value(code, "hourly", station.station_type, rng)}
                    for code in HOURLY_FACTOR
                ]
                result = measurement_service.record_entries(
                    station_id=station.id,
                    measured_at=datetime(day.year, day.month, day.day, hour, 0),
                    period="hourly",
                    entries=hourly_entries,
                    data_source="manual",
                    recorder=rng.choice(recorder_pool),
                )
                totals["measurements"] += result["summary"]["created_count"]
                totals["exceedances"] += result["summary"]["exceeded_count"]

    # 标注一部分超标记录, 让工作台同时存在待办与已处理记录
    from .services import exceedance_service

    exceedances = Exceedance.query.order_by(Exceedance.id.asc()).all()
    annotated = 0
    for index, record in enumerate(exceedances):
        if index % 3 == 0:
            continue
        if index % 3 == 1:
            exceedance_service.annotate(
                record, status="confirmed", note="数据经复核属实, 已通知运维排查周边排放源",
                annotator=rng.choice(recorder_pool),
            )
        else:
            exceedance_service.annotate(
                record, status="ignored", note="仪器校准期间异常值, 已在原始数据中标记无效",
                annotator=rng.choice(recorder_pool),
            )
        annotated += 1
    totals["annotated"] = annotated

    totals.update(_seed_inspections(created_stations, rng))
    return totals


def _seed_inspections(stations, rng):
    """Generate inspection plans / tasks / work orders covering every lifecycle state."""
    from .domain import inspection as catalog
    from .services import inspection_service, work_order_service

    today = date.today()
    by_code = {station.code: station for station in stations}

    all_codes = [item["code"] for item in catalog.INSPECTION_ITEMS]
    short_codes = ["env_cabinet", "sampler", "analyzer", "data_acquisition", "power_network"]

    def make_plan(name, cycle, station_objs, start_offset, item_codes, inspector,
                  next_offset=None, enabled=True):
        start = today + timedelta(days=start_offset)
        plan = InspectionPlan(
            name=name, cycle=cycle, items=item_codes, enabled=enabled,
            start_date=start, next_run_date=today + timedelta(days=next_offset or start_offset),
            inspector=inspector, remark=None,
        )
        plan.stations = list(station_objs)
        db.session.add(plan)
        db.session.flush()
        return plan

    # 周期计划: 每日(全市运行点位)、每周(重点站点)、每月
    daily_plan = make_plan(
        "运行点位每日例行巡检", "daily",
        [s for s in stations if s.status == "active"],
        start_offset=0, item_codes=short_codes, inspector="李静",
    )
    weekly_plan = make_plan(
        "重点站点每周设备巡检", "weekly",
        [by_code["SZ-AQ-003"], by_code["SZ-AQ-005"]],
        start_offset=2, item_codes=all_codes, inspector="王敏", next_offset=2,
    )
    make_plan(
        "全站月度全面巡检", "monthly",
        [s for s in stations if s.status != "offline"],
        start_offset=6, item_codes=all_codes, inspector="陈志强", next_offset=6,
    )

    def make_task(station, due, plan=None, inspector=None, item_codes=None):
        task = InspectionTask(
            code=inspection_service._make_code("XJ", due),
            plan_id=plan.id if plan else None,
            station_id=station.id, status="pending", due_date=due,
            inspector=inspector or (plan.inspector if plan else None),
            items_snapshot=catalog.snapshot(item_codes or (plan.items if plan else short_codes)),
        )
        db.session.add(task)
        db.session.flush()
        from .models import InspectionTaskItem
        for snap in task.items_snapshot:
            db.session.add(InspectionTaskItem(
                task_id=task.id, item_code=snap["code"],
                item_name=snap["name"], category=snap["category"],
            ))
        return task

    # 1) 昨天已完成的一次正常巡检 (市民中心站)
    done = make_task(by_code["SZ-AQ-001"], today - timedelta(days=1),
                     plan=daily_plan, inspector="李静")
    for idx, row in enumerate(done.task_items):
        row.result = "na" if row.item_code == "calibration" else "normal"
        row.checked_at = datetime.combine(done.due_date, datetime.min.time()).replace(hour=10 + idx)
        row.inspector = "李静"
    done.status = "completed"
    done.started_at = datetime.combine(done.due_date, datetime.min.time()).replace(hour=9, minute=30)
    done.finished_at = datetime.combine(done.due_date, datetime.min.time()).replace(hour=11)
    done.summary = "设备运行正常, 数据上传稳定"

    # 2) 昨天巡检异常 -> 已转单且已修复, 点位恢复运行中 (华侨城站)
    abn_done = make_task(by_code["SZ-AQ-002"], today - timedelta(days=2),
                         plan=daily_plan, inspector="王敏")
    for idx, row in enumerate(abn_done.task_items):
        if row.item_code == "sampler":
            row.result = "abnormal"
            row.remark = "采样管路疑似堵塞, 流量偏低"
        else:
            row.result = "normal"
        row.checked_at = datetime.combine(abn_done.due_date, datetime.min.time()).replace(hour=9 + idx)
        row.inspector = "王敏"
    abn_done.status = "abnormal"
    abn_done.abnormal_count = 1
    abn_done.started_at = datetime.combine(abn_done.due_date, datetime.min.time()).replace(hour=9)
    abn_done.finished_at = datetime.combine(abn_done.due_date, datetime.min.time()).replace(hour=10)
    abn_done.summary = "采样系统异常, 已转维修"
    order = work_order_service.create_work_order(
        station_id=abn_done.station_id,
        title="华侨城站采样管路堵塞",
        description="巡检发现采样流量偏低, 判断为管路积尘堵塞",
        priority="high", reporter="王敏", assignee="赵宇", source="inspection",
        task_item=next(r for r in abn_done.task_items if r.item_code == "sampler"),
        inspection_task=abn_done, commit=False,
    )
    order.reported_at = datetime.combine(abn_done.due_date, datetime.min.time()).replace(hour=11)
    work_order_service.transition(order, "processing")
    order.started_at = datetime.combine(abn_done.due_date, datetime.min.time()).replace(hour=14)
    work_order_service.transition(
        order, "resolved", resolution="已清洗采样管路并更换前置滤芯, 流量恢复正常",
        restore_status="active",
    )
    order.resolved_at = datetime.combine(today - timedelta(days=1), datetime.min.time()).replace(hour=16)
    work_order_service.transition(order, "closed")

    # 3) 今天巡检异常 -> 维修工单待处理, 点位被自动置为维护中 (罗湖口岸站)
    abn_today = make_task(by_code["SZ-AQ-003"], today,
                          plan=weekly_plan, inspector="陈志强")
    for idx, row in enumerate(abn_today.task_items):
        if row.item_code == "analyzer":
            row.result = "abnormal"
            row.remark = "NOx 分析仪光源报警, 测量值漂移"
        elif row.item_code in {"env_cabinet", "sampler", "data_acquisition"}:
            row.result = "normal"
        else:
            row.result = None
        if row.result:
            row.checked_at = datetime.combine(today, datetime.min.time()).replace(hour=9 + idx)
            row.inspector = "陈志强"
    abn_today.status = "in_progress"
    abn_today.abnormal_count = 1
    abn_today.started_at = datetime.combine(today, datetime.min.time()).replace(hour=9)
    open_order = work_order_service.create_work_order(
        station_id=abn_today.station_id,
        title="罗湖口岸站 NOx 分析仪光源故障",
        description="巡检发现光源报警且测量值漂移, 需更换光源组件",
        priority="urgent", reporter="陈志强", assignee="赵宇", source="inspection",
        task_item=next(r for r in abn_today.task_items if r.item_code == "analyzer"),
        inspection_task=abn_today, due_date=today + timedelta(days=2), commit=False,
    )
    open_order.reported_at = datetime.combine(today, datetime.min.time()).replace(hour=10, minute=20)
    work_order_service.transition(open_order, "processing", assignee="赵宇")

    # 4) 今天待执行的巡检任务 (宝安中心站)
    make_task(by_code["SZ-AQ-004"], today, plan=daily_plan, inspector="孙倩")

    # 5) 昨天到期未执行 -> 已逾期 (龙岗工业园站)
    make_task(by_code["SZ-AQ-005"], today - timedelta(days=1),
              plan=weekly_plan, inspector="王敏")

    # 6) 大鹏站: 计划巡检正常但另有一张处理中的人工工单, 点位台账显示维护中
    if "SZ-AQ-007" in by_code:
        depot = by_code["SZ-AQ-007"]
        depot_task = make_task(depot, today - timedelta(days=3), inspector="孙倩")
        for idx, row in enumerate(depot_task.task_items):
            row.result = "normal"
            row.checked_at = datetime.combine(
                depot_task.due_date, datetime.min.time()
            ).replace(hour=9 + idx)
            row.inspector = "孙倩"
        depot_task.status = "completed"
        depot_task.started_at = datetime.combine(
            depot_task.due_date, datetime.min.time()
        ).replace(hour=9)
        depot_task.finished_at = datetime.combine(
            depot_task.due_date, datetime.min.time()
        ).replace(hour=10)
        manual = work_order_service.create_work_order(
            station_id=depot.id,
            title="大鹏生态站数采传输模块更换",
            description="数采仪通信模块老化频繁掉线, 已申请备件",
            priority="normal", reporter="孙倩", assignee="赵宇", source="manual",
            due_date=today + timedelta(days=3), commit=False,
        )
        work_order_service.transition(manual, "processing", assignee="赵宇")

    db.session.commit()
    inspection_service.mark_overdue(today)
    db.session.commit()

    return {
        "inspection_plans": InspectionPlan.query.count(),
        "inspection_tasks": InspectionTask.query.count(),
        "work_orders": WorkOrder.query.count(),
    }


def reset_database():
    db.drop_all()
    db.create_all()


def ensure_bootstrap(app):
    """Create tables / seed demo data at startup when enabled by config."""
    auto_init = app.config.get("AUTO_INIT_DB")
    auto_seed = app.config.get("AUTO_SEED")
    if not auto_init and not auto_seed:
        return
    with app.app_context():
        try:
            if auto_init:
                db.create_all()
            if auto_seed and db.session.query(Station.id).first() is None:
                app.logger.info("seeding demo data ...")
                seed_demo_data()
        except Exception as exc:  # pragma: no cover - depends on external database
            app.logger.warning("bootstrap skipped: %s", exc)
