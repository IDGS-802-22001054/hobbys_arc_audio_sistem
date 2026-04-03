from flask import Blueprint

stock_empleado_bp = Blueprint("stock_empleado", __name__)

from . import routes
