from flask import Blueprint

publico_bp = Blueprint(
    'index', 
    __name__,
    template_folder='../../templates'
)

from . import pagina_routes
