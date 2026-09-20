"""演示数据生成与启动引导."""
import json
import random
from datetime import date, datetime, timedelta

from .extensions import db
from .models import Exceedance, InspectionPlan, Measurement, RepairOrder, Station

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
    return totals


# ---- 运维巡检演示数据 -------------------------------------------------------
INSPECTION_PLAN_DEMO = [
    # (station_code, name, cycle, items, assignee)
    ("SZ-AQ-001", "市民中心站例行巡检", "weekly",
     ["采样管路清洁与密封性", "分析仪运行状态与报警", "数据采集与传输链路", "供电系统与UPS续航"], "李静"),
    ("SZ-AQ-003", "罗湖口岸站周巡检", "weekly",
     ["采样管路清洁与密封性", "分析仪运行状态与报警", "站房温湿度与空调", "站房安全与环境卫生"], "王敏"),
    ("SZ-AQ-005", "龙岗工业园站月度巡检", "monthly",
     ["采样管路清洁与密封性", "分析仪运行状态与报警", "数据采集与传输链路",
      "标准气体与校准记录", "防雷与接地装置"], "陈志强"),
    ("SZ-AQ-006", "梧桐山背景站季度巡检", "quarterly",
     ["供电系统与UPS续航", "防雷与接地装置", "站房安全与环境卫生"], "赵宇"),
]


def seed_inspection_data(recorder_pool=RECORDERS):
    """生成巡检计划/任务/工单演示数据, 覆盖闭环的各个状态."""
    from .services import inspection_service, repair_service

    rng = random.Random(20260920)
    stations = {station.code: station for station in Station.query.all()}
    totals = {"plans": 0, "tasks": 0, "repairs": 0}

    plans = []
    for code, name, cycle, items, assignee in INSPECTION_PLAN_DEMO:
        station = stations.get(code)
        if station is None:
            continue
        plan = inspection_service.create_plan(
            {
                "station_id": station.id,
                "name": name,
                "cycle": cycle,
                "items": json.dumps(items, ensure_ascii=False),
                "assignee": assignee,
                "active": True,
            }
        )
        plans.append(plan)
    totals["plans"] = len(plans)

    # 1) 已完成且正常的任务: 直接构造历史记录
    normal_plan = next((plan for plan in plans if plan.cycle == "quarterly"), plans[0])
    task, created = inspection_service.dispatch_plan(normal_plan)
    if created:
        inspection_service.complete_task(
            task,
            items=[{"id": item.id, "result": "normal", "note": ""} for item in task.items],
            executor=normal_plan.assignee,
            summary="各项检查正常, 设备运行稳定",
        )
        totals["tasks"] += 1

    # 2) 已完成且异常 -> 已生成工单并修复: 台账状态回写为运行中
    if len(plans) >= 3:
        resolved_plan = plans[2]
        task, created = inspection_service.dispatch_plan(resolved_plan)
        if created:
            item_payloads = []
            for index, item in enumerate(task.items):
                if index == 1:
                    item_payloads.append(
                        {"id": item.id, "result": "abnormal", "note": "分析仪响应迟缓, 零点漂移超限"}
                    )
                else:
                    item_payloads.append({"id": item.id, "result": "normal", "note": ""})
            task, repair = inspection_service.complete_task(
                task,
                items=item_payloads,
                executor=resolved_plan.assignee,
                summary="分析仪存在零点漂移, 已转维修工单处理",
                repair_data={"priority": "high", "title": "分析仪零点漂移维修"},
            )
            totals["tasks"] += 1
            if repair:
                repair_service.resolve_repair(
                    repair,
                    resolution="已更换分析仪光源模块并重新校准, 零点漂移恢复正常",
                    handler="孙倩",
                    station_status_after="active",
                )
                totals["repairs"] += 1

    # 3) 已完成且异常 -> 工单待处理: 台账保持维护中, 出现在待办列表
    if len(plans) >= 2:
        abnormal_plan = plans[1]
        task, created = inspection_service.dispatch_plan(abnormal_plan)
        if created:
            item_payloads = []
            for index, item in enumerate(task.items):
                if index == 2:
                    item_payloads.append(
                        {"id": item.id, "result": "abnormal", "note": "站房空调制冷不足, 温度持续偏高"}
                    )
                else:
                    item_payloads.append({"id": item.id, "result": "normal", "note": ""})
            task, repair = inspection_service.complete_task(
                task,
                items=item_payloads,
                executor=abnormal_plan.assignee,
                summary="站房温湿度超标, 需维修空调",
                repair_data={"priority": "urgent", "title": "站房空调维修"},
            )
            totals["tasks"] += 1
            if repair:
                totals["repairs"] += 1

    # 4) 待执行任务: 保留在待办列表
    if plans:
        task, created = inspection_service.dispatch_plan(plans[0])
        if created:
            totals["tasks"] += 1

    # 5) 手工报修工单 (处理中), 来源非巡检
    manual_station = stations.get("SZ-AQ-004")
    if manual_station:
        repair = repair_service.create_repair(
            manual_station,
            {
                "title": "数据采集器间歇性掉线",
                "description": "运维值班发现数据平台夜间多次断连, 怀疑采集器SIM卡接触不良",
                "priority": "medium",
                "reporter": rng.choice(recorder_pool),
                "handler": "赵宇",
            },
        )
        totals["repairs"] += 1

    return totals


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
                seed_inspection_data()
        except Exception as exc:  # pragma: no cover - depends on external database
            app.logger.warning("bootstrap skipped: %s", exc)
