"""Configuration explicite des trois moteurs pris en charge."""

from pathlib import Path
from django.core.exceptions import ImproperlyConfigured


def database_config(base_dir, env):
    engine = env.get("DB_ENGINE", "sqlite").strip().lower()
    if engine == "sqlite":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": Path(base_dir) / "db.sqlite3",
            "OPTIONS": {"timeout": 20},
        }
    if engine in ("postgresql", "postgres", "pgsql"):
        options = {"connect_timeout": 10}
        if env.get("DB_SSLMODE"):
            options["sslmode"] = env["DB_SSLMODE"]
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.get("DB_NAME", "estfbs_django"),
            "USER": env.get("DB_USER", "estfbs_app"),
            "PASSWORD": env.get("DB_PASSWORD", ""),
            "HOST": env.get("DB_HOST", "127.0.0.1"),
            "PORT": env.get("DB_PORT", "5432"),
            "OPTIONS": options,
        }
    if engine == "mysql":
        return {
            "ENGINE": "django.db.backends.mysql",
            "NAME": env.get("DB_NAME", "estfbs_django"),
            "USER": env.get("DB_USER", "root"),
            "PASSWORD": env.get("DB_PASSWORD", ""),
            "HOST": env.get("DB_HOST", "127.0.0.1"),
            "PORT": env.get("DB_PORT", "3306"),
            "OPTIONS": {
                "charset": "utf8mb4",
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    raise ImproperlyConfigured("DB_ENGINE doit être sqlite, postgresql ou mysql.")
