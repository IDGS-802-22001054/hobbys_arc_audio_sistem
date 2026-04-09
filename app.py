from flask import Flask, render_template, redirect, url_for, request
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, current_user,  logout_user
from config import DevelopmentConfig
from models import db, Usuario
from sqlalchemy import text
from extensions import mail

from blueprints.catalogo_cliente import catalogo_cliente_bp
from blueprints.compras import compras_bp
from blueprints.ventas.routes import ventas_bp
from blueprints.materia_prima import materia_prima_bp
from blueprints.proveedores import proveedores_bp
from blueprints.stock_empleado import stock_empleado_bp
from blueprints.dashboard.routes_dashboard import dashboard_bp
from blueprints.clientes.routes_cliente import clientes_bp
from blueprints.auth.routes_auth import auth_bp
from blueprints.empleados.routes_empleado import empleados_bp
from blueprints.producción.routes_produccion import produccion_bp

migracion = Migrate()
proteccion_csrf = CSRFProtect()
login_manager = LoginManager()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesión para continuar'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))


def inicializar_base_datos(aplicacion):
    with aplicacion.app_context():
        db.metadata.tables


def registrar_blueprints(aplicacion):
    aplicacion.register_blueprint(catalogo_cliente_bp)
    aplicacion.register_blueprint(stock_empleado_bp)
    aplicacion.register_blueprint(proveedores_bp)
    aplicacion.register_blueprint(materia_prima_bp)
    aplicacion.register_blueprint(compras_bp)
    aplicacion.register_blueprint(ventas_bp)
    aplicacion.register_blueprint(dashboard_bp)
    aplicacion.register_blueprint(auth_bp)
    aplicacion.register_blueprint(empleados_bp)
    aplicacion.register_blueprint(clientes_bp)
    aplicacion.register_blueprint(produccion_bp)


def registrar_manejadores_error(aplicacion):
    @aplicacion.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template("index.html"), 404


def registrar_context_processors(aplicacion):
    @aplicacion.context_processor
    def inject_notifications():
        es_autorizado = True
        alertas = []

        if es_autorizado:
            query = text("""
                SELECT IdAlertaSistema, Mensaje, ReferenciaId
                FROM alertasistema
                WHERE Leida = 0 AND TipoAlerta = 'STOCK_BAJO'
                ORDER BY FechaGeneracion DESC
            """)
            alertas = db.session.execute(query).fetchall()

        return dict(
            alertas_criticas=alertas,
            total_alertas=len(alertas),
            puede_ver_alertas=es_autorizado,
        )


def crear_app():
    aplicacion = Flask(__name__)
    aplicacion.config.from_object(DevelopmentConfig)

    aplicacion.config['MAIL_SERVER'] = 'smtp.gmail.com'
    aplicacion.config['MAIL_PORT'] = 587
    aplicacion.config['MAIL_USE_TLS'] = True
    aplicacion.config['MAIL_USERNAME'] = 'dannabr564@gmail.com'
    aplicacion.config['MAIL_PASSWORD'] = 'pxtozmsewsbblrzu'
    aplicacion.config['MAIL_DEFAULT_SENDER'] = ('Hobbys Car Audio', 'dannabr564@gmail.com')

    db.init_app(aplicacion)
    mail.init_app(aplicacion)
    migracion.init_app(aplicacion, db)
    proteccion_csrf.init_app(aplicacion)
    login_manager.init_app(aplicacion)

    @aplicacion.before_request
    def verificar_cambio_credenciales():
        rutas_libres = {
            'auth.login',
            'auth.logout',
            'empleados.cambiar_credenciales',
            'static',
        }
        if (
            current_user.is_authenticated
            and getattr(current_user, 'DebeCambiarCredenciales', False)
            and request.endpoint not in rutas_libres
        ):
            return redirect(url_for('empleados.cambiar_credenciales'))

    inicializar_base_datos(aplicacion)
    registrar_blueprints(aplicacion)
    registrar_manejadores_error(aplicacion)
    registrar_context_processors(aplicacion)

    return aplicacion

    @app.after_request
    def no_cache(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response

app = crear_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", True))