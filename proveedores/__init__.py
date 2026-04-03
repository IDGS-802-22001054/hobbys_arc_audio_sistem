from flask import Blueprint

proveedores_bp = Blueprint(
    'proveedores', 
    __name__,
    template_folder='templates'
)

from . import p_routes