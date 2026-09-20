"""维修工单: 巡检异常转单或人工建单, 完成后回写台账运行状态."""
from ..domain.constants import (
    WORK_ORDER_PRIORITY_LABELS,
    WORK_ORDER_SOURCE_LABELS,
    WORK_ORDER_STATUS_LABELS,
    label_of,
)
from ..extensions import db
from .base import TimestampMixin, iso, iso_date


class WorkOrder(TimestampMixin, db.Model):
    __tablename__ = "work_orders"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_item_id = db.Column(
        db.Integer,
        db.ForeignKey("inspection_task_items.id", ondelete="SET NULL"),
        unique=True,
        index=True,
    )
    inspection_task_id = db.Column(
        db.Integer, db.ForeignKey("inspection_tasks.id", ondelete="SET NULL"), index=True
    )
    source = db.Column(db.String(16), nullable=False, default="inspection", index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(16), nullable=False, default="normal")
    status = db.Column(db.String(16), nullable=False, default="open", index=True)
    reporter = db.Column(db.String(64))
    assignee = db.Column(db.String(64))
    reported_at = db.Column(db.DateTime, nullable=False)
    started_at = db.Column(db.DateTime)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)
    resolution = db.Column(db.Text)  # 维修处理说明
    restore_status = db.Column(db.String(32))  # 办结后期望台账回写的状态, 默认 active
    due_date = db.Column(db.Date)

    station = db.relationship("Station")
    task_item = db.relationship("InspectionTaskItem", back_populates="work_order")
    inspection_task = db.relationship("InspectionTask", foreign_keys=[inspection_task_id])

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "station_id": self.station_id,
            "station_name": self.station.name if self.station else None,
            "station_code": self.station.code if self.station else None,
            "station_area": self.station.area if self.station else None,
            "task_item_id": self.task_item_id,
            "inspection_task_id": self.inspection_task_id,
            "inspection_task_code": self.inspection_task.code if self.inspection_task else None,
            "item_name": self.task_item.item_name if self.task_item else None,
            "source": self.source,
            "source_label": label_of(WORK_ORDER_SOURCE_LABELS, self.source),
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "priority_label": label_of(WORK_ORDER_PRIORITY_LABELS, self.priority),
            "status": self.status,
            "status_label": label_of(WORK_ORDER_STATUS_LABELS, self.status),
            "reporter": self.reporter,
            "assignee": self.assignee,
            "reported_at": iso(self.reported_at),
            "started_at": iso(self.started_at),
            "resolved_at": iso(self.resolved_at),
            "closed_at": iso(self.closed_at),
            "resolution": self.resolution,
            "restore_status": self.restore_status,
            "due_date": iso_date(self.due_date),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }

    def __repr__(self):
        return "<WorkOrder %s %s>" % (self.code, self.status)
