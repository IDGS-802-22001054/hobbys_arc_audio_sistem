from flask import Blueprint

costos_utilidades_bp = Blueprint(
    'costos_utilidades', 
    __name__,
    template_folder= 'templates'
)

from . import cu_routes