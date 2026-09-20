"""巡检项目录与计划编制规则.

巡检项以稳定的 ``code`` 作为快照主键: 派发任务时把计划绑定的巡检项
快照写入巡检任务明细, 后续即使目录文案调整也不影响已派发的任务。
"""

INSPECTION_ITEMS = [
    {"code": "env_cabinet", "name": "站房环境与机柜", "category": "环境",
     "description": "站房温湿度、卫生整洁、机柜无积尘漏水"},
    {"code": "sampler", "name": "采样系统检查", "category": "采样",
     "description": "采样头、管路气密性, 无堵塞漏气"},
    {"code": "analyzer", "name": "分析仪运行状态", "category": "设备",
     "description": "分析仪指示灯、流量、量程与报警信息正常"},
    {"code": "calibration", "name": "校准与标气", "category": "校准",
     "description": "标气压力充足, 近期零点/跨度校准记录合格"},
    {"code": "data_acquisition", "name": "数采仪与数据上传", "category": "通信",
     "description": "数采仪在线, 监测数据按时上传无缺失"},
    {"code": "power_network", "name": "供电与网络", "category": "保障",
     "description": "UPS 电量正常, 网络链路稳定无频繁掉线"},
    {"code": "gas_consumables", "name": "耗材与试剂余量", "category": "耗材",
     "description": "滤膜、试剂等耗材余量满足下一周期使用"},
    {"code": "safety_fire", "name": "防雷消防与安全", "category": "安全",
     "description": "灭火器在有效期, 防雷接地完好, 无安全隐患"},
]

CATEGORY_LABEL = "巡检分类"


def all_items():
    return [dict(item) for item in INSPECTION_ITEMS]


def item_map(codes):
    """Return catalog rows for the given codes, preserving the requested order."""
    catalog = {item["code"]: dict(item) for item in INSPECTION_ITEMS}
    result = []
    for code in codes:
        item = catalog.get(code)
        if item:
            result.append(item)
    return result


def known_codes():
    return {item["code"] for item in INSPECTION_ITEMS}


def snapshot(codes):
    """Minimal JSON-serialisable snapshot stored on every dispatched task item."""
    return [
        {"code": item["code"], "name": item["name"], "category": item["category"]}
        for item in item_map(codes)
    ]
