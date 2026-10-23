import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-not-secure")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://exam_user:exam_pass@localhost:3306/exam_optimizer?charset=utf8mb4",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = 3600 * 8

    INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "Demo University")
    DEFAULT_SAFETY_MARGIN = int(os.environ.get("DEFAULT_SAFETY_MARGIN", "0"))
    SOLVER_MAX_TIME_SECONDS = int(os.environ.get("SOLVER_MAX_TIME_SECONDS", "30"))

    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_LOCKOUT_SECONDS = 300

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL",
        "mysql+pymysql://exam_user:exam_pass@localhost:3306/exam_optimizer_test?charset=utf8mb4",
    )


_CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config(name: str | None = None):
    name = name or os.environ.get("FLASK_ENV", "default")
    return _CONFIGS.get(name, DevelopmentConfig)