from datetime import date, datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_apscheduler import APScheduler
from flask_login import LoginManager, current_user, logout_user
from config import DevelopmentConfig
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text
from extensions import mail
from services.db_connection import configure_dynamic_mysql_users
from services.db_role import register_role_management

from blueprints.auth.routes_auth import auth_bp
from blueprints.catalogo_cliente import catalogo_cliente_bp
from blueprints.clientes.routes_cliente import clientes_bp
from blueprints.compras import compras_bp
from blueprints.configuracion_sistema import configuracion_sistema_bp
from blueprints.costos_utilidades import costos_utilidades_bp
from blueprints.dashboard.routes_dashboard import dashboard_bp
from blueprints.empleados.routes_empleado import empleados_bp
from blueprints.materia_prima import materia_prima_bp
from blueprints.produccion.routes_produccion import produccion_bp
from blueprints.proveedores import proveedores_bp
from blueprints.costos_utilidades.cu_routes import costos_utilidades_bp
from blueprints.stock_empleado import stock_empleado_bp
from blueprints.ventas import ventas_bp
from blueprints.pagina.pagina_routes import publico_bp

from models import CorteVentaDiario, SesionUsuario, SolicitudProduccion, Usuario, db

from services.configuracion import (
    alertas_materia_prima_habilitadas,
    obtener_duracion_inactividad_sesion,
    obtener_milisegundos_inactividad_sesion,
)
from services.produccion import TIPO_ALERTA_PEDIDO_CLIENTE

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


def realizar_corte_automatico(app):
    with app.app_context():
        ayer = date.today() - timedelta(days=1)
        existe = CorteVentaDiario.query.filter_by(FechaCorte=ayer).first()
        if not existe:
            db.session.add(CorteVentaDiario(
                FechaCorte=ayer,
                IdUsuarioRegistro=1,
            ))
            db.session.commit()


def inicializar_base_datos(app):
    with app.app_context():
        db.metadata.tables


def registrar_blueprints(app):
    app.register_blueprint(catalogo_cliente_bp)
    app.register_blueprint(stock_empleado_bp)
    app.register_blueprint(proveedores_bp)
    app.register_blueprint(materia_prima_bp)
    app.register_blueprint(compras_bp)
    app.register_blueprint(costos_utilidades_bp)
    app.register_blueprint(configuracion_sistema_bp)
    app.register_blueprint(ventas_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(empleados_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(produccion_bp)
    app.register_blueprint(publico_bp)


def registrar_manejadores_error(app):
    @app.errorhandler(403)
    def acceso_prohibido(error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template("index.html"), 404


def crear_app():
    app = Flask(__name__)
    app.config.from_object(DevelopmentConfig)
    configure_dynamic_mysql_users(app)

    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'dannabr564@gmail.com'
    app.config['MAIL_PASSWORD'] = 'pxtozmsewsbblrzu'
    app.config['MAIL_DEFAULT_SENDER'] = ('Hobbys Car Audio', 'dannabr564@gmail.com')

    db.init_app(app)
    mail.init_app(app)
    migracion.init_app(app, db)
    proteccion_csrf.init_app(app)
    login_manager.init_app(app)
    scheduler.init_app(app)
    with app.app_context():
        register_role_management(app, db)

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @scheduler.task('cron', id='corte_diario_job', hour=0, minute=0)
    def job_corte():
        realizar_corte_automatico(app)

    scheduler.start()

    inicializar_base_datos(app)
    registrar_blueprints(app)
    for endpoint, vista in app.view_functions.items():
        if endpoint.startswith('catalogo_cliente.api_'):
            proteccion_csrf.exempt(vista)
    registrar_manejadores_error(app)
    registrar_manejadores_sesion(app)
    registrar_context_processors(app)

    return app

def registrar_manejadores_sesion(app):

    def obtener_sesion():
        id_sesion = session.get('id_sesion_usuario')
        if id_sesion:
            sesion = db.session.get(SesionUsuario, id_sesion)
            if sesion and sesion.Activa and sesion.IdUsuario == current_user.IdUsuario:
                return sesion

        return (
            db.session.query(SesionUsuario)
            .filter_by(IdUsuario=current_user.IdUsuario, Activa=True)
            .order_by(SesionUsuario.FechaInicio.desc())
            .first()
        )

    @app.before_request
    def validar_sesion():
        if not current_user.is_authenticated:
            return None

        if request.endpoint in (None, 'static'):
            return None

        sesion = obtener_sesion()

        if not sesion:
            session.clear()
            logout_user()
            flash("Tu sesión ya no está activa.", "warning")
            return redirect(url_for("auth.login"))

        ahora = datetime.now()
        limite = obtener_duracion_inactividad_sesion()

        if sesion.FechaUltimaActividad and (ahora - sesion.FechaUltimaActividad > limite):
            sesion.Activa = False
            sesion.FechaCierre = ahora
            sesion.MotivoCierre = "inactividad"

            try:
                db.session.commit()
            except:
                db.session.rollback()

            session.clear()
            logout_user()
            flash("Sesión cerrada por inactividad.", "warning")
            return redirect(url_for("auth.login"))

        if not sesion.FechaUltimaActividad or (ahora - sesion.FechaUltimaActividad > timedelta(minutes=1)):
            sesion.FechaUltimaActividad = ahora
            try:
                db.session.commit()
            except:
                db.session.rollback()

        session['id_sesion_usuario'] = sesion.IdSesionUsuario
        return None

def registrar_context_processors(aplicacion):
    @aplicacion.context_processor
    def inject_notifications():
        alertas = []
        alertas_cliente = []
        solicitudes_pendientes = []
        alertas_mp_habilitadas = alertas_materia_prima_habilitadas()

        rol_actual = (
            getattr(getattr(current_user, 'rol', None), 'Nombre', '')
            if getattr(current_user, 'is_authenticated', False)
            else ''
        )

        es_admin = rol_actual == 'Administrador'
        es_autorizado = rol_actual in ['Administrador', 'Almacenista']
        es_cliente = bool(getattr(getattr(current_user, 'persona', None), 'cliente', None)) if getattr(current_user, 'is_authenticated', False) else False

        if es_autorizado and alertas_mp_habilitadas:
            query = text("""
                SELECT IdAlertaSistema, Mensaje, ReferenciaId, TipoAlerta
                FROM alertasistema
                WHERE Leida = 0 AND TipoAlerta = 'STOCK_BAJO'
                ORDER BY FechaGeneracion DESC
            """)
            alertas = list(db.session.execute(query).fetchall())

        if es_admin and alertas_mp_habilitadas:
            query_alertas_produccion = text("""
                SELECT IdAlertaSistema, Mensaje, ReferenciaId, TipoAlerta
                FROM alertasistema
                WHERE Leida = 0
                  AND TipoAlerta = 'MATERIAL_INSUFICIENTE'
                  AND IdUsuarioDestino = :id_usuario
                ORDER BY FechaGeneracion DESC
            """)
            alertas.extend(
                db.session.execute(
                    query_alertas_produccion,
                    {'id_usuario': current_user.IdUsuario},
                ).fetchall()
            )

        if es_admin:
            query_solicitudes = text("""
                SELECT
                    sp.IdSolicitudProduccion,
                    sp.CantidadSolicitada,
                    sp.FechaSolicitud,
                    pt.Nombre AS NombreProducto,
                    per.Nombre AS NombreSolicita,
                    per.Apellidos AS ApellidosSolicita
                FROM SolicitudProduccion sp
                INNER JOIN ProductoTerminado pt
                    ON pt.IdProductoTerminado = sp.IdProductoTerminado
                INNER JOIN Usuario u
                    ON u.IdUsuario = sp.IdUsuarioSolicita
                INNER JOIN Persona per
                    ON per.IdPersona = u.IdPersona
                WHERE sp.Estado = 'PENDIENTE'
                ORDER BY sp.FechaSolicitud DESC
            """)
            solicitudes_pendientes = db.session.execute(query_solicitudes).fetchall()

        if es_cliente:
            query_alertas_cliente = text("""
                SELECT IdAlertaSistema, Mensaje, ReferenciaId, TipoAlerta, FechaGeneracion
                FROM alertasistema
                WHERE Leida = 0
                  AND TipoAlerta = :tipo_alerta
                  AND IdUsuarioDestino = :id_usuario
                ORDER BY FechaGeneracion DESC
            """)
            alertas_cliente = db.session.execute(
                query_alertas_cliente,
                {'tipo_alerta': TIPO_ALERTA_PEDIDO_CLIENTE, 'id_usuario': current_user.IdUsuario},
            ).fetchall()

        return dict(
            alertas_criticas=alertas,
            alertas_cliente=alertas_cliente,
            solicitudes_pendientes=solicitudes_pendientes,
            total_alertas=len(alertas) + len(solicitudes_pendientes) + len(alertas_cliente),
            puede_ver_alertas=es_autorizado,
            puede_aprobar_solicitudes=es_admin,
            inactividad_timeout_ms=obtener_milisegundos_inactividad_sesion(),
        )

app = crear_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", True))
