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

# ---- 运维巡检 --------------------------------------------------------
INSPECTION_CYCLE_LABELS = {"daily": "每日", "weekly": "每周", "monthly": "每月", "once": "单次"}

INSPECTION_TASK_STATUS_LABELS = {
    "pending": "待执行",
    "in_progress": "执行中",
    "abnormal": "巡检异常",
    "completed": "已完成",
    "overdue": "已逾期",
}

INSPECTION_RESULT_LABELS = {"normal": "正常", "abnormal": "异常", "na": "不适用"}

WORK_ORDER_STATUS_LABELS = {
    "open": "待维修",
    "processing": "维修中",
    "resolved": "已修复",
    "closed": "已关闭",
    "cancelled": "已取消",
}

WORK_ORDER_PRIORITY_LABELS = {"low": "低", "normal": "中", "high": "高", "urgent": "紧急"}

WORK_ORDER_SOURCE_LABELS = {"inspection": "巡检转单", "manual": "人工建单"}

# 工单处于这些状态时, 对应点位台账应显示为“维护中”
WORK_ORDER_ACTIVE_STATUSES = ("open", "processing")
# 巡检任务处于这些状态时仍属于待办
INSPECTION_TASK_TODO_STATUSES = ("pending", "in_progress", "overdue")


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
        "inspection_result": as_options(INSPECTION_RESULT_LABELS),
        "work_order_status": as_options(WORK_ORDER_STATUS_LABELS),
        "work_order_priority": as_options(WORK_ORDER_PRIORITY_LABELS),
        "work_order_source": as_options(WORK_ORDER_SOURCE_LABELS),
    }


def label_of(label_map, key):
    return label_map.get(key, key)
