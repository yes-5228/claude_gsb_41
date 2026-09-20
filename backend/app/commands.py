"""Flask CLI commands: flask init-db / seed / reset-db."""
import click

from .extensions import db
from .models import (
    Exceedance,
    InspectionPlan,
    InspectionTask,
    Measurement,
    Station,
    WorkOrder,
)


def register_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        db.create_all()
        click.echo("数据库表已创建")

    @app.cli.command("seed")
    @click.option("--days", default=5, show_default=True, help="生成最近多少天的数据")
    @click.option("--force", is_flag=True, help="已有数据时仍然追加写入")
    def seed(days, force):
        """Load demo stations and monitoring records."""
        from .seed import seed_demo_data

        if Station.query.count() and not force:
            click.echo("已存在监测点数据, 如确需追加请使用 --force")
            return
        db.create_all()
        totals = seed_demo_data(days=days)
        click.echo(
            "演示数据写入完成: 监测点 %(stations)s 个, 监测数据 %(measurements)s 条, "
            "超标记录 %(exceedances)s 条" % totals
        )

    @app.cli.command("reset-db")
    @click.option("--with-demo/--empty", default=True, help="是否写入演示数据")
    def reset_db(with_demo):
        """Drop all tables, recreate them and optionally load demo data."""
        from .seed import reset_database, seed_demo_data

        reset_database()
        click.echo("数据库已重置")
        if with_demo:
            totals = seed_demo_data()
            click.echo("演示数据写入完成: %s" % totals)

    @app.cli.command("stats")
    def stats():
        """Print a short record summary."""
        click.echo(
            "监测点 %d 个 / 监测数据 %d 条 / 超标记录 %d 条 / 巡检计划 %d 个 / "
            "巡检任务 %d 条 / 维修工单 %d 张"
            % (
                Station.query.count(),
                Measurement.query.count(),
                Exceedance.query.count(),
                InspectionPlan.query.count(),
                InspectionTask.query.count(),
                WorkOrder.query.count(),
            )
        )

    @app.cli.command("dispatch-inspections")
    def dispatch_inspections():
        """Dispatch due recurring inspection plans (meant to run daily via cron)."""
        from .services import inspection_service

        result = inspection_service.dispatch_due_plans()
        click.echo(
            "巡检派发完成: 到期计划 %d 个, 生成巡检任务 %d 条"
            % (result["dispatched_plan_count"], result["task_count"])
        )
