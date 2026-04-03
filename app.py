from flask import Flask, render_template
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from blueprints.catalogo_cliente import catalogo_cliente_bp
from blueprints.catalogo_cliente.routes import obtener_contexto_catalogo
from blueprints.stock_empleado import stock_empleado_bp
from proveedores import proveedores_bp
from materia_prima import materia_prima_bp
from compras import compras_bp
from config import DevelopmentConfig
from models import db
from flask import session
from sqlalchemy import text

migracion = Migrate()
proteccion_csrf = CSRFProtect()


def inicializar_base_datos(aplicacion):
    with aplicacion.app_context():
        db.metadata.tables


def registrar_blueprints(aplicacion):
    aplicacion.register_blueprint(catalogo_cliente_bp)
    aplicacion.register_blueprint(stock_empleado_bp)
    aplicacion.register_blueprint(proveedores_bp)
    aplicacion.register_blueprint(materia_prima_bp)
    aplicacion.register_blueprint(compras_bp)


def registrar_manejadores_error(aplicacion):
    @aplicacion.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template("index.html"), 404

def registrar_context_processors(aplicacion):
    @aplicacion.context_processor
    def inject_notifications():
        es_autorizado = True
        # es_autorizado = session.get('rol') in ['Administrador', 'Almacenista']
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
            puede_ver_alertas=es_autorizado
        )


def crear_app():
    aplicacion = Flask(__name__)
    aplicacion.config.from_object(DevelopmentConfig)

    db.init_app(aplicacion)
    migracion.init_app(aplicacion, db)
    proteccion_csrf.init_app(aplicacion)

    inicializar_base_datos(aplicacion)
    registrar_blueprints(aplicacion)
    registrar_manejadores_error(aplicacion)

    return aplicacion


app = crear_app()


if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))
