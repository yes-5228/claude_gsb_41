"""巡检任务 (计划派发或人工创建) 与逐项结果."""
from ..domain.constants import (
    INSPECTION_RESULT_LABELS,
    INSPECTION_TASK_STATUS_LABELS,
    label_of,
)
from ..extensions import db
from .base import TimestampMixin, iso, iso_date


class InspectionTask(TimestampMixin, db.Model):
    __tablename__ = "inspection_tasks"
    __table_args__ = (
        # 同一计划对同一点位同一天只允许派发一次, 防止周期任务重复
        db.UniqueConstraint(
            "plan_id", "station_id", "due_date", name="uq_inspection_plan_station_due"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(40), unique=True, nullable=False, index=True)
    plan_id = db.Column(
        db.Integer, db.ForeignKey("inspection_plans.id", ondelete="SET NULL"), index=True
    )
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    due_date = db.Column(db.Date, nullable=False, index=True)
    inspector = db.Column(db.String(64))
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    summary = db.Column(db.Text)  # 巡检整体说明
    abnormal_count = db.Column(db.Integer, nullable=False, default=0)
    items_snapshot = db.Column(db.JSON, nullable=False, default=list)  # 派发时巡检项目录快照

    plan = db.relationship("InspectionPlan", back_populates="tasks")
    station = db.relationship("Station")
    task_items = db.relationship(
        "InspectionTaskItem",
        back_populates="task",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="InspectionTaskItem.id",
    )

    def result_progress(self):
        total = len(self.task_items)
        recorded = sum(1 for item in self.task_items if item.result is not None)
        abnormal = sum(1 for item in self.task_items if item.result == "abnormal")
        return {"total": total, "recorded": recorded, "abnormal": abnormal}

    def to_dict(self, include_items=False, include_plan=False):
        progress = self.result_progress()
        payload = {
            "id": self.id,
            "code": self.code,
            "plan_id": self.plan_id,
            "station_id": self.station_id,
            "station_name": self.station.name if self.station else None,
            "station_code": self.station.code if self.station else None,
            "station_area": self.station.area if self.station else None,
            "station_status": self.station.status if self.station else None,
            "status": self.status,
            "status_label": label_of(INSPECTION_TASK_STATUS_LABELS, self.status),
            "due_date": iso_date(self.due_date),
            "inspector": self.inspector,
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
            "summary": self.summary,
            "abnormal_count": self.abnormal_count,
            "items_snapshot": list(self.items_snapshot or []),
            "plan_name": self.plan.name if self.plan else None,
            "progress": progress,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_items:
            payload["items"] = [item.to_dict() for item in self.task_items]
        if include_plan and self.plan:
            payload["plan"] = self.plan.to_dict()
        return payload

    def __repr__(self):
        return "<InspectionTask %s %s>" % (self.code, self.status)


class InspectionTaskItem(db.Model):
    __tablename__ = "inspection_task_items"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer,
        db.ForeignKey("inspection_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_code = db.Column(db.String(48), nullable=False)
    item_name = db.Column(db.String(120), nullable=False)
    category = db.Column(db.String(48))
    result = db.Column(db.String(16))  # normal / abnormal / na, None = 未检查
    remark = db.Column(db.Text)
    checked_at = db.Column(db.DateTime)
    inspector = db.Column(db.String(64))

    task = db.relationship("InspectionTask", back_populates="task_items")
    work_order = db.relationship(
        "WorkOrder",
        back_populates="task_item",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def to_dict(self):
        return {
            "id": self.id,
            "task_id": self.task_id,
            "item_code": self.item_code,
            "item_name": self.item_name,
            "category": self.category,
            "result": self.result,
            "result_label": label_of(INSPECTION_RESULT_LABELS, self.result) if self.result else "未检查",
            "remark": self.remark,
            "checked_at": iso(self.checked_at),
            "inspector": self.inspector,
            "work_order_id": self.work_order.id if self.work_order else None,
            "work_order_status": self.work_order.status if self.work_order else None,
        }

    def __repr__(self):
        return "<InspectionTaskItem %s %s>" % (self.item_code, self.result)
