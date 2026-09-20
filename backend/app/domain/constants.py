"""Enumerations shared by the API layer and the frontend."""

PERIOD_LABELS = {"hourly": "小时均值", "daily": "日均值"}

DATA_SOURCE_LABELS = {"manual": "手工录入", "device": "设备上传", "import": "历史导入"}

STATION_TYPE_LABELS = {
    "ambient": "环境空气",
    "traffic": "道路交通",
    "background": "区域背景",
    "industrial": "工业园区",
    "rural": "农村站点",
}

STATION_STATUS_LABELS = {"active": "运行中", "maintenance": "维护中", "offline": "停用"}

EXCEEDANCE_LEVEL_LABELS = {"light": "轻度超标", "moderate": "中度超标", "severe": "重度超标"}

EXCEEDANCE_STATUS_LABELS = {"pending": "待标注", "confirmed": "已确认", "ignored": "已忽略"}

# ---- 运维巡检 ----
INSPECTION_CYCLE_LABELS = {"weekly": "每周", "monthly": "每月", "quarterly": "每季度"}

INSPECTION_TASK_STATUS_LABELS = {
    "pending": "待执行",
    "in_progress": "执行中",
    "completed": "已完成",
    "cancelled": "已取消",
}

INSPECTION_RESULT_LABELS = {"normal": "正常", "abnormal": "异常"}

INSPECTION_ITEM_RESULT_LABELS = {
    "pending": "待检",
    "normal": "正常",
    "abnormal": "异常",
    "skipped": "未检",
}

# 巡检项目录: 计划模板与手工派发时从中勾选
INSPECTION_ITEM_CATALOG = (
    "采样管路清洁与密封性",
    "分析仪运行状态与报警",
    "数据采集与传输链路",
    "供电系统与UPS续航",
    "站房温湿度与空调",
    "标准气体与校准记录",
    "防雷与接地装置",
    "站房安全与环境卫生",
)

REPAIR_PRIORITY_LABELS = {"low": "低", "medium": "中", "high": "高", "urgent": "紧急"}

REPAIR_STATUS_LABELS = {
    "open": "待处理",
    "processing": "处理中",
    "resolved": "已修复",
    "closed": "已关闭",
}


def as_options(label_map):
    return [{"value": key, "label": label} for key, label in label_map.items()]


def options_payload():
    return {
        "station_type": as_options(STATION_TYPE_LABELS),
        "station_status": as_options(STATION_STATUS_LABELS),
        "period": as_options(PERIOD_LABELS),
        "data_source": as_options(DATA_SOURCE_LABELS),
        "exceedance_level": as_options(EXCEEDANCE_LEVEL_LABELS),
        "exceedance_status": as_options(EXCEEDANCE_STATUS_LABELS),
        "inspection_cycle": as_options(INSPECTION_CYCLE_LABELS),
        "inspection_task_status": as_options(INSPECTION_TASK_STATUS_LABELS),
        "inspection_item_result": as_options(INSPECTION_ITEM_RESULT_LABELS),
        "repair_priority": as_options(REPAIR_PRIORITY_LABELS),
        "repair_status": as_options(REPAIR_STATUS_LABELS),
    }


def label_of(label_map, key):
    return label_map.get(key, key)
