"""Utilidades de linea de comandos. Uso: python -m app.cli set-password <contrasena>"""

import base64
import sys

from app.security import hash_password


def main() -> None:
    if len(sys.argv) != 3 or sys.argv[1] != "set-password":
        print("Uso: python -m app.cli set-password <contrasena>")
        raise SystemExit(1)

    password_hash = hash_password(sys.argv[2])
    encoded = base64.b64encode(password_hash.encode()).decode()
    print("Añade esto a tu .env como APP_PASSWORD_HASH_B64:")
    print("(se guarda en base64 para evitar que Docker Compose corrompa el '$' del hash bcrypt)")
    print(encoded)


if __name__ == "__main__":
    main()
