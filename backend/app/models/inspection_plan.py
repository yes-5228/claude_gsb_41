"""巡检计划: 按周期为监测点批量派发巡检任务."""
from ..domain.constants import INSPECTION_CYCLE_LABELS, label_of
from ..extensions import db
from .base import TimestampMixin, iso, iso_date

# 计划与监测点的多对多绑定
plan_station = db.Table(
    "inspection_plan_stations",
    db.Column("plan_id", db.Integer,
              db.ForeignKey("inspection_plans.id", ondelete="CASCADE"), primary_key=True),
    db.Column("station_id", db.Integer,
              db.ForeignKey("stations.id", ondelete="CASCADE"), primary_key=True),
)


class InspectionPlan(TimestampMixin, db.Model):
    __tablename__ = "inspection_plans"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    cycle = db.Column(db.String(16), nullable=False, default="weekly", index=True)
    items = db.Column(db.JSON, nullable=False, default=list)  # 巡检项 code 列表 (目录快照主键)
    enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    start_date = db.Column(db.Date, nullable=False)
    next_run_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date)
    inspector = db.Column(db.String(64))
    remark = db.Column(db.Text)

    stations = db.relationship(
        "Station",
        secondary=plan_station,
        passive_deletes=True,
    )
    tasks = db.relationship(
        "InspectionTask",
        back_populates="plan",
        passive_deletes=True,
    )

    def station_id_list(self):
        return [station.id for station in self.stations]

    def to_dict(self, include_stations=False):
        payload = {
            "id": self.id,
            "name": self.name,
            "cycle": self.cycle,
            "cycle_label": label_of(INSPECTION_CYCLE_LABELS, self.cycle),
            "items": list(self.items or []),
            "station_ids": self.station_id_list(),
            "enabled": bool(self.enabled),
            "start_date": iso_date(self.start_date),
            "next_run_date": iso_date(self.next_run_date),
            "end_date": iso_date(self.end_date),
            "inspector": self.inspector,
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_stations:
            payload["stations"] = [station.to_option() for station in self.stations]
        return payload

    def __repr__(self):
        return "<InspectionPlan %s %s>" % (self.id, self.name)
