from flask import Blueprint, render_template
from flask_login import login_required

produccion_bp = Blueprint('produccion', __name__, url_prefix='/produccion')

@produccion_bp.route('/produccion')
@login_required
def produccion():
    return render_template('produccion/producciones.html', active='produccion')