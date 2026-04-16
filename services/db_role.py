from __future__ import annotations

import logging
import unicodedata

from flask import has_request_context, session
from sqlalchemy import event, text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

_ROLE_BY_APP_ROLE = {
    "administrador": "Administrador",
    "vendedor": "Vendedor",
    "almacenista": "Almacenista",
    "produccion": "Produccion",
    "consulta": "Consulta",
    "cliente": "Cliente",
}


def _normalizar_nombre_rol(nombre: str | None) -> str:
    texto = unicodedata.normalize("NFKD", (nombre or "").strip().lower())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _rol_mysql_desde_usuario() -> str | None:
    if not has_request_context():
        return None

    rol = session.get("app_role_nombre")
    if not rol:
        return None

    return _ROLE_BY_APP_ROLE.get(_normalizar_nombre_rol(rol))


def _rol_mysql_activo(app) -> str | None:
    rol_request = _rol_mysql_desde_usuario()
    if rol_request:
        return rol_request

    return app.config.get("MYSQL_FALLBACK_ROLE")


def register_role_management(app, db):
    if app.extensions.get("mysql_role_management_registered"):
        return

    engine = db.engine
    session_factory = db.session.session_factory

    @event.listens_for(engine, "checkout")
    def _reset_role_on_checkout(dbapi_connection, connection_record, connection_proxy):
        cursor = None
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("SET ROLE NONE")
        except Exception as error:
            logger.warning("No fue posible ejecutar SET ROLE NONE al tomar conexion: %s", error)
        finally:
            if cursor is not None:
                cursor.close()

    @event.listens_for(session_factory, "after_begin")
    def _apply_role_after_begin(session, transaction, connection):
        rol_mysql = _rol_mysql_activo(app)
        if not rol_mysql:
            return

        try:
            connection.execute(text(f"SET ROLE `{rol_mysql}`"))
        except SQLAlchemyError as error:
            logger.warning("No fue posible ejecutar SET ROLE `%s`: %s", rol_mysql, error)
            if app.config.get("MYSQL_ENFORCE_SET_ROLE"):
                raise RuntimeError(
                    f"No fue posible activar el rol MySQL `{rol_mysql}` para esta sesion."
                ) from error

    app.extensions["mysql_role_management_registered"] = True
