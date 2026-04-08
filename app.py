from flask import Flask, render_template
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from config import DevelopmentConfig
from models import db, Usuario
from sqlalchemy import text

from blueprints.catalogo_cliente import catalogo_cliente_bp
from blueprints.compras import compras_bp
from blueprints.ventas.routes import ventas_bp
from blueprints.materia_prima import materia_prima_bp
from blueprints.proveedores import proveedores_bp
from blueprints.costos_utilidades import costos_utilidades_bp
from blueprints.stock_empleado import stock_empleado_bp
from blueprints.ventas import ventas_bp
from dashboard.routes_dashboard import dashboard_bp
from clientes.routes_cliente import clientes_bp
from auth.routes_auth import auth_bp
from empleados.routes_empleado import empleados_bp
from config import DevelopmentConfig
from models import db, Usuario
from models import db, CorteVentaDiario
from flask import session
from sqlalchemy import text
from flask_apscheduler import APScheduler
from datetime import date, timedelta

migracion = Migrate()
proteccion_csrf = CSRFProtect()
scheduler = APScheduler()

login_manager = LoginManager()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesión para continuar'
login_manager.login_message_category = 'warning'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

def realizar_corte_automatico(aplicacion):
    with aplicacion.app_context():
        ayer = date.today() - timedelta(days=1)
        existe = CorteVentaDiario.query.filter_by(FechaCorte=ayer).first()
        if not existe:
            nuevo_corte = CorteVentaDiario(
                FechaCorte=ayer,
                IdUsuarioRegistro=1 
            )
            db.session.add(nuevo_corte)
            db.session.commit()

def inicializar_base_datos(aplicacion):
    with aplicacion.app_context():
        db.metadata.tables


def registrar_blueprints(aplicacion):
    aplicacion.register_blueprint(catalogo_cliente_bp)
    aplicacion.register_blueprint(stock_empleado_bp)
    aplicacion.register_blueprint(proveedores_bp)
    aplicacion.register_blueprint(materia_prima_bp)
    aplicacion.register_blueprint(compras_bp)
    aplicacion.register_blueprint(costos_utilidades_bp)
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
        es_autorizado = session.get('rol') in ['Administrador', 'Almacenista']
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

    db.init_app(aplicacion)
    migracion.init_app(aplicacion, db)
    proteccion_csrf.init_app(aplicacion)
    login_manager.init_app(aplicacion)
    scheduler.init_app(aplicacion)
    
    @scheduler.task('cron', id='corte_diario_job', hour=0, minute=0)
    def job_corte():
        realizar_corte_automatico(aplicacion)
        
    scheduler.start()

    login_manager.init_app(aplicacion)

    inicializar_base_datos(aplicacion)
    registrar_blueprints(aplicacion)
    registrar_manejadores_error(aplicacion)
    registrar_context_processors(aplicacion)

    return aplicacion


app = crear_app()


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", True))
