from flask import Blueprint

materia_prima_bp = Blueprint(
    'materia_prima', 
    __name__,
    template_folder='../../templates'
)

from . import mp_routes
