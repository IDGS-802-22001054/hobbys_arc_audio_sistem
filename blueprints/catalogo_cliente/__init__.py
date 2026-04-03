from flask import Blueprint

catalogo_cliente_bp = Blueprint("catalogo_cliente", __name__)

from . import routes
