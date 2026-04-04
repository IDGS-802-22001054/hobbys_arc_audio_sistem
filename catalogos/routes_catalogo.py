from flask import Blueprint, render_template
from flask_login import login_required

catalogo_bp = Blueprint('catalogo', __name__)

@catalogo_bp.route('/catalogo')
@login_required
def catalogo():
    return render_template('catalogo/catalogo.html')