"""运维巡检: 计划 / 任务 / 巡检项结果."""
import json

from ..domain.constants import (
    INSPECTION_CYCLE_LABELS,
    INSPECTION_ITEM_RESULT_LABELS,
    INSPECTION_RESULT_LABELS,
    INSPECTION_TASK_STATUS_LABELS,
    STATION_STATUS_LABELS,
    label_of,
)
from ..extensions import db
from .base import TimestampMixin, iso, iso_date


class InspectionPlan(TimestampMixin, db.Model):
    """巡检计划: 为点位配置巡检周期与巡检项模板, 按周期派发任务."""

    __tablename__ = "inspection_plans"

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name = db.Column(db.String(120), nullable=False)
    cycle = db.Column(db.String(16), nullable=False, default="monthly")
    items = db.Column(db.Text, nullable=False, default="[]")  # JSON 数组: 巡检项模板
    assignee = db.Column(db.String(64))
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    remark = db.Column(db.Text)

    station = db.relationship("Station", back_populates="inspection_plans")
    tasks = db.relationship(
        "InspectionTask",
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def item_list(self):
        try:
            items = json.loads(self.items or "[]")
        except ValueError:
            return []
        return [str(item) for item in items if str(item).strip()]

    def to_dict(self, include_station=True):
        payload = {
            "id": self.id,
            "station_id": self.station_id,
            "name": self.name,
            "cycle": self.cycle,
            "cycle_label": label_of(INSPECTION_CYCLE_LABELS, self.cycle),
            "items": self.item_list(),
            "assignee": self.assignee,
            "active": bool(self.active),
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_station and self.station:
            payload["station_name"] = self.station.name
            payload["station_code"] = self.station.code
            payload["station_area"] = self.station.area
        return payload

    def __repr__(self):
        return "<InspectionPlan %s station=%s>" % (self.name, self.station_id)


class InspectionTask(TimestampMixin, db.Model):
    """巡检任务: 按计划周期派发或手工临时派发, 逐项记录结果后完成."""

    __tablename__ = "inspection_tasks"
    __table_args__ = (
        db.UniqueConstraint("plan_id", "period_key", name="uq_inspection_task_plan_period"),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(
        db.Integer, db.ForeignKey("inspection_plans.id", ondelete="CASCADE"), index=True
    )
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_key = db.Column(db.String(16), nullable=False, default="")
    title = db.Column(db.String(160), nullable=False)
    cycle = db.Column(db.String(16), nullable=False, default="monthly")
    due_date = db.Column(db.Date)
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    assignee = db.Column(db.String(64))
    executor = db.Column(db.String(64))
    dispatched_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    result = db.Column(db.String(16))  # normal / abnormal, 完成时回写
    summary = db.Column(db.Text)
    remark = db.Column(db.Text)

    plan = db.relationship("InspectionPlan", back_populates="tasks")
    station = db.relationship("Station", back_populates="inspection_tasks")
    items = db.relationship(
        "InspectionItemResult",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InspectionItemResult.id",
    )
    repair_orders = db.relationship("RepairOrder", back_populates="inspection_task")

    def abnormal_items(self):
        return [item for item in self.items if item.result == "abnormal"]

    def to_dict(self, include_items=False, include_repairs=False):
        payload = {
            "id": self.id,
            "plan_id": self.plan_id,
            "station_id": self.station_id,
            "period_key": self.period_key,
            "title": self.title,
            "cycle": self.cycle,
            "cycle_label": label_of(INSPECTION_CYCLE_LABELS, self.cycle),
            "due_date": iso_date(self.due_date),
            "status": self.status,
            "status_label": label_of(INSPECTION_TASK_STATUS_LABELS, self.status),
            "assignee": self.assignee,
            "executor": self.executor,
            "dispatched_at": iso(self.dispatched_at),
            "started_at": iso(self.started_at),
            "completed_at": iso(self.completed_at),
            "result": self.result,
            "result_label": label_of(INSPECTION_RESULT_LABELS, self.result) if self.result else None,
            "summary": self.summary,
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
            "station_name": self.station.name if self.station else None,
            "station_code": self.station.code if self.station else None,
            "station_area": self.station.area if self.station else None,
            "station_status": self.station.status if self.station else None,
            "station_status_label": label_of(STATION_STATUS_LABELS, self.station.status)
            if self.station
            else None,
            "plan_name": self.plan.name if self.plan else None,
            "item_total": len(self.items),
            "abnormal_count": len(self.abnormal_items()),
            "repair_count": len(self.repair_orders),
        }
        if include_items:
            payload["items"] = [item.to_dict() for item in self.items]
        if include_repairs:
            payload["repair_orders"] = [order.to_dict() for order in self.repair_orders]
        return payload

    def __repr__(self):
        return "<InspectionTask %s %s>" % (self.id, self.title)


class InspectionItemResult(TimestampMixin, db.Model):
    """巡检项结果: 派发时按模板预生成, 执行时逐项填写."""

    __tablename__ = "inspection_item_results"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("inspection_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_name = db.Column(db.String(120), nullable=False)
    result = db.Column(db.String(16), nullable=False, default="pending")
    note = db.Column(db.Text)

    task = db.relationship("InspectionTask", back_populates="items")

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "item_name": self.item_name,
            "result": self.result,
            "result_label": label_of(INSPECTION_ITEM_RESULT_LABELS, self.result),
            "note": self.note,
            "updated_at": iso(self.updated_at),
        }

    def __repr__(self):
        return "<InspectionItemResult %s %s=%s>" % (self.task_id, self.item_name, self.result)
