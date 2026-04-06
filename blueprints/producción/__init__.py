from flask import Blueprint 

producciones = Blueprint(
    'producciones',
    __name__,
    template_folder = 'templates'

)

from . import routes_produccion