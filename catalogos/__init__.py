from flask import Blueprint 

catalogos = Blueprint(
    'catalogos',
    __name__,
    template_folder = 'templates'

)

from . import routes_catalogo