from flask import Flask, render_template
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from blueprints.catalogo_cliente import catalogo_cliente_bp
from blueprints.catalogo_cliente.routes import obtener_contexto_catalogo
from blueprints.stock_empleado import stock_empleado_bp
from config import DevelopmentConfig
from models import db

migracion = Migrate()
proteccion_csrf = CSRFProtect()


def inicializar_base_datos(aplicacion):
    with aplicacion.app_context():
        db.metadata.tables


def registrar_blueprints(aplicacion):
    aplicacion.register_blueprint(catalogo_cliente_bp)
    aplicacion.register_blueprint(stock_empleado_bp)


def registrar_manejadores_error(aplicacion):
    @aplicacion.errorhandler(404)
    def pagina_no_encontrada(error):
        return render_template("index.html"), 404


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
