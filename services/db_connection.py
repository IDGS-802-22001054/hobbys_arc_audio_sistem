from __future__ import annotations

import unicodedata

import pymysql
from flask import has_request_context, session
from sqlalchemy.engine.url import make_url
from sqlalchemy.pool import NullPool


_DB_USER_BY_APP_ROLE = {
    "administrador": "admin_app",
    "vendedor": "vendedor_app",
    "almacenista": "almacen_app",
    "produccion": "produccion_app",
    "consulta": "consulta_app",
    "cliente": "cliente_app",
}


def _normalizar_nombre_rol(nombre: str | None) -> str:
    texto = unicodedata.normalize("NFKD", (nombre or "").strip().lower())
    return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))


def _usuario_mysql_desde_request() -> str | None:
    if not has_request_context():
        return None

    rol = session.get("app_role_nombre")
    if not rol:
        return None

    return _DB_USER_BY_APP_ROLE.get(_normalizar_nombre_rol(rol))


def configure_dynamic_mysql_users(app):
    if app.extensions.get("dynamic_mysql_users_configured"):
        return

    url = make_url(app.config["SQLALCHEMY_DATABASE_URI"])
    if not url.drivername.startswith("mysql"):
        return

    password = app.config.get("MYSQL_ROLE_DB_PASSWORD", "Cont5445")
    fallback_user = app.config.get("MYSQL_FALLBACK_DB_USER", "admin_app")

    def _creator():
        username = _usuario_mysql_desde_request() or fallback_user
        return pymysql.connect(
            host=url.host or "localhost",
            port=int(url.port or 3306),
            user=username,
            password=password,
            database=url.database,
            charset="utf8mb4",
            autocommit=False,
        )

    engine_options = dict(app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {}))
    engine_options["poolclass"] = NullPool
    engine_options["creator"] = _creator
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options
    app.extensions["dynamic_mysql_users_configured"] = True
