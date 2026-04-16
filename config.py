class Config(object):
    SECRET_KEY = 'Clave nueva'
    SESSION_COOKIE_SECURE = False
import os


def _entero_env(nombre):
    valor = os.getenv(nombre)
    if valor in (None, ""):
        return None
    try:
        return int(valor)
    except ValueError:
        return None


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MYSQL_FALLBACK_ROLE = os.getenv("MYSQL_FALLBACK_ROLE", "Administrador")
    MYSQL_FALLBACK_DB_USER = os.getenv("MYSQL_FALLBACK_DB_USER", "admin_app")
    MYSQL_ROLE_DB_PASSWORD = os.getenv("MYSQL_ROLE_DB_PASSWORD", "Cont5445")
    MYSQL_ENFORCE_SET_ROLE = os.getenv("MYSQL_ENFORCE_SET_ROLE", "0") == "1"
    CATALOGO_USUARIO_REGISTRO_ID = _entero_env("CATALOGO_USUARIO_REGISTRO_ID")
    CATALOGO_CLIENTE_ID = _entero_env("CATALOGO_CLIENTE_ID")


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL", "mysql+pymysql://admin_app:Cont5445@localhost/hobbys_car_audio"
    )
