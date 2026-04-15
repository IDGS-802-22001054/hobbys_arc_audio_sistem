from flask import Blueprint

configuracion_sistema_bp = Blueprint(
    'configuracion_sistema',
    __name__,
    template_folder='../../templates'
)

from . import routes_configuracion
