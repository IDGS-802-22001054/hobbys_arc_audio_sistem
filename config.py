

class Config(object):
    SECRET_KEY = 'Clave nueva'
    SESSION_COOKIE_SECURE = False

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI='mysql+pymysql://root:root@127.0.0.1/Hobbys'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
