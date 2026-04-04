from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from config import DevelopmentConfig
from models import db, Usuario
from auth.routes_auth import auth_bp
from empleados.routes_empleado import empleados_bp
from clientes.routes_cliente import clientes_bp
from dashboard.routes_dashboard import dashboard_bp
from catalogos.routes_catalogo import catalogo_bp

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)

csrf = CSRFProtect(app)
db.init_app(app)


app.register_blueprint(dashboard_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(empleados_bp)
app.register_blueprint(clientes_bp)
app.register_blueprint(catalogo_bp)

login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesión para continuar'
login_manager.login_message_category = 'warning'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)