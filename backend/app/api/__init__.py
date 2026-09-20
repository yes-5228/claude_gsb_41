"""Blueprint registration."""
from .exceedances import bp as exceedances_bp
from .inspections import bp as inspections_bp
from .measurements import bp as measurements_bp
from .meta import bp as meta_bp
from .query import bp as query_bp
from .repairs import bp as repairs_bp
from .stations import bp as stations_bp

BLUEPRINTS = (
    (meta_bp, "/api/meta"),
    (stations_bp, "/api/stations"),
    (measurements_bp, "/api/measurements"),
    (exceedances_bp, "/api/exceedances"),
    (inspections_bp, "/api/inspections"),
    (repairs_bp, "/api/repairs"),
    (query_bp, "/api/query"),
)


def register_blueprints(app):
    for blueprint, url_prefix in BLUEPRINTS:
        app.register_blueprint(blueprint, url_prefix=url_prefix)
