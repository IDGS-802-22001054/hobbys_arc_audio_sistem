from flask import Blueprint 

empleados = Blueprint(
    'empleados',
    __name__,
    template_folder = 'templates'

)

from . import routes_empleado