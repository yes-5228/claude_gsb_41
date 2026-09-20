"""维修工单: 巡检异常或手工报修产生, 处理完成后回写台账运行状态."""
from ..domain.constants import (
    REPAIR_PRIORITY_LABELS,
    REPAIR_STATUS_LABELS,
    STATION_STATUS_LABELS,
    label_of,
)
from ..extensions import db
from .base import TimestampMixin, iso


class RepairOrder(TimestampMixin, db.Model):
    __tablename__ = "repair_orders"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    inspection_task_id = db.Column(
        db.Integer, db.ForeignKey("inspection_tasks.id", ondelete="SET NULL"), index=True
    )
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(16), nullable=False, default="medium", index=True)
    status = db.Column(db.String(16), nullable=False, default="open", index=True)
    reporter = db.Column(db.String(64))
    handler = db.Column(db.String(64))
    station_status_before = db.Column(db.String(32))  # 报修时台账状态快照
    station_status_after = db.Column(db.String(32))  # 处理完成后回写的台账状态
    resolution = db.Column(db.Text)
    resolved_at = db.Column(db.DateTime)
    closed_at = db.Column(db.DateTime)

    station = db.relationship("Station", back_populates="repair_orders")
    inspection_task = db.relationship("InspectionTask", back_populates="repair_orders")

    def to_dict(self):
        return {
            "id": self.id,
            "code": self.code,
            "station_id": self.station_id,
            "inspection_task_id": self.inspection_task_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "priority_label": label_of(REPAIR_PRIORITY_LABELS, self.priority),
            "status": self.status,
            "status_label": label_of(REPAIR_STATUS_LABELS, self.status),
            "reporter": self.reporter,
            "handler": self.handler,
            "station_status_before": self.station_status_before,
            "station_status_after": self.station_status_after,
            "resolution": self.resolution,
            "resolved_at": iso(self.resolved_at),
            "closed_at": iso(self.closed_at),
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "station_name": self.station.name if self.station else None,
            "station_code": self.station.code if self.station else None,
            "station_area": self.station.area if self.station else None,
            "station_status": self.station.status if self.station else None,
            "station_status_label": label_of(STATION_STATUS_LABELS, self.station.status)
            if self.station
            else None,
            "inspection_task_title": self.inspection_task.title if self.inspection_task else None,
        }

    def __repr__(self):
        return "<RepairOrder %s %s>" % (self.code, self.title)
