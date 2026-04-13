from flask import Flask, render_template
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, current_user
from config import DevelopmentConfig
from models import db, Usuario, SolicitudProduccion
from sqlalchemy import text
from blueprints.produccion.routes_produccion import produccion_bp
from blueprints.catalogo_cliente import catalogo_cliente_bp
from blueprints.compras import compras_bp
from blueprints.ventas.routes import ventas_bp
from blueprints.materia_prima import materia_prima_bp
from blueprints.proveedores import proveedores_bp
from blueprints.costos_utilidades import costos_utilidades_bp
from blueprints.stock_empleado import stock_empleado_bp
from blueprints.ventas import ventas_bp
from blueprints.dashboard.routes_dashboard import dashboard_bp
from blueprints.clientes.routes_cliente import clientes_bp
from blueprints.auth.routes_auth import auth_bp
from blueprints.empleados.routes_empleado import empleados_bp
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
        alertas = []
        solicitudes_pendientes = []
        rol_actual = (
            getattr(getattr(current_user, 'rol', None), 'Nombre', '')
            if getattr(current_user, 'is_authenticated', False)
            else ''
        )
        es_admin = rol_actual == 'Administrador'
        es_autorizado = rol_actual in ['Administrador', 'Almacenista']

        if es_autorizado:
            query = text("""
                SELECT IdAlertaSistema, Mensaje, ReferenciaId, TipoAlerta
                FROM alertasistema
                WHERE Leida = 0 AND TipoAlerta = 'STOCK_BAJO'
                ORDER BY FechaGeneracion DESC
            """)
            alertas = list(db.session.execute(query).fetchall())

        if es_admin:
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
                    {'id_usuario': current_user.IdUsuario}
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
