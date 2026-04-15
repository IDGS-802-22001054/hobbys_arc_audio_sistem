from flask import Flask, render_template, redirect, url_for, request
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, current_user, logout_user
from config import DevelopmentConfig
from models import db, Usuario, SolicitudProduccion
from sqlalchemy import text
from extensions import mail

from blueprints.produccion.routes_produccion import produccion_bp
from datetime import date, datetime, timedelta

from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_apscheduler import APScheduler
from flask_login import LoginManager, current_user, logout_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import text

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
from blueprints.dashboard.routes_dashboard import dashboard_bp
from blueprints.clientes.routes_cliente import clientes_bp
from blueprints.auth.routes_auth import auth_bp
from blueprints.empleados.routes_empleado import empleados_bp

from blueprints.stock_empleado import stock_empleado_bp
from blueprints.ventas import ventas_bp
from config import DevelopmentConfig
from models import CorteVentaDiario, SesionUsuario, SolicitudProduccion, Usuario, db
from services.configuracion import (
    alertas_materia_prima_habilitadas,
    obtener_duracion_inactividad_sesion,
    obtener_milisegundos_inactividad_sesion,
)

migracion = Migrate()
proteccion_csrf = CSRFProtect()
scheduler = APScheduler()

login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Inicia sesiÃ³n para continuar'
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
                IdUsuarioRegistro=1,
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
    aplicacion.register_blueprint(configuracion_sistema_bp)
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
        alertas = []
        solicitudes_pendientes = []
        alertas_mp_habilitadas = alertas_materia_prima_habilitadas()
        rol_actual = (
            getattr(getattr(current_user, 'rol', None), 'Nombre', '')
            if getattr(current_user, 'is_authenticated', False)
            else ''
        )
        es_admin = rol_actual == 'Administrador'
        es_autorizado = rol_actual in ['Administrador', 'Almacenista']

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

        return dict(
            alertas_criticas=alertas,
            solicitudes_pendientes=solicitudes_pendientes,
            total_alertas=len(alertas) + len(solicitudes_pendientes),
            puede_ver_alertas=es_autorizado,
            puede_aprobar_solicitudes=es_admin,
            inactividad_timeout_ms=obtener_milisegundos_inactividad_sesion(),
        )


def registrar_manejadores_sesion(aplicacion):
    def _obtener_sesion_activa_usuario():
        id_sesion = session.get('id_sesion_usuario')
        if id_sesion:
            sesion_activa = db.session.get(SesionUsuario, id_sesion)
            if (
                sesion_activa is not None
                and sesion_activa.IdUsuario == current_user.IdUsuario
                and sesion_activa.Activa
            ):
                return sesion_activa

        return (
            db.session.query(SesionUsuario)
            .filter_by(IdUsuario=current_user.IdUsuario, Activa=True)
            .order_by(SesionUsuario.FechaInicio.desc())
            .first()
        )

    @aplicacion.before_request
    def controlar_inactividad_sesion():
        if not getattr(current_user, 'is_authenticated', False):
            return None

        if request.endpoint in (None, 'static'):
            return None

        sesion_activa = _obtener_sesion_activa_usuario()
        if sesion_activa is None:
            session.pop('id_sesion_usuario', None)
            logout_user()
            flash('Tu sesion ya no esta activa. Inicia sesion nuevamente.', 'warning')
            return redirect(url_for('auth.login'))

        ahora = datetime.now()
        ultima_actividad = sesion_activa.FechaUltimaActividad or sesion_activa.FechaInicio or ahora
        limite_inactividad = obtener_duracion_inactividad_sesion()

        if ahora - ultima_actividad >= limite_inactividad:
            sesion_activa.Activa = False
            sesion_activa.FechaCierre = ahora
            sesion_activa.MotivoCierre = 'inactividad'
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

            session.pop('id_sesion_usuario', None)
            logout_user()
            flash('Tu sesion se cerro por inactividad.', 'warning')
            return redirect(url_for('auth.login'))

        if ahora - ultima_actividad >= timedelta(minutes=1):
            sesion_activa.FechaUltimaActividad = ahora
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

        if 'id_sesion_usuario' not in session:
            session['id_sesion_usuario'] = sesion_activa.IdSesionUsuario

        return None


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
    scheduler.init_app(aplicacion)

    @scheduler.task('cron', id='corte_diario_job', hour=0, minute=0)
    def job_corte():
        realizar_corte_automatico(aplicacion)

    scheduler.start()

    inicializar_base_datos(aplicacion)
    registrar_blueprints(aplicacion)
    registrar_manejadores_error(aplicacion)
    registrar_manejadores_sesion(aplicacion)
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