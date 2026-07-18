"""Entrypoint del contenedor, válido para Docker Compose y para el add-on de Home Assistant.

- Si existe /data/options.json (Home Assistant Supervisor), mapea las opciones del
  add-on a variables de entorno.
- Aplica las migraciones de base de datos (alembic upgrade head) en cada arranque.
- Lanza uvicorn.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HA_OPTIONS = Path("/data/options.json")

OPTION_TO_ENV = {
    "username": "APP_USERNAME",
    "password": "APP_PASSWORD",
    "secret_key": "SECRET_KEY",
    "app_name": "APP_NAME",
    "currency": "DEFAULT_CURRENCY",
}


def main() -> None:
    if HA_OPTIONS.exists():
        options = json.loads(HA_OPTIONS.read_text())
        for option, env_name in OPTION_TO_ENV.items():
            value = options.get(option)
            if value not in (None, ""):
                os.environ[env_name] = str(value)
        os.environ.setdefault("DATABASE_URL", "sqlite:////data/miney.db")
        os.environ.setdefault("DATA_DIR", "/data")
        os.environ.setdefault("UPLOAD_DIR", "/data/uploads")

    Path(os.environ.get("DATA_DIR", "./data")).mkdir(parents=True, exist_ok=True)

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)

    os.execvp("uvicorn", ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"])


if __name__ == "__main__":
    main()
