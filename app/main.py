from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.auth import AuthMiddleware
from app.config import get_settings
from app.routers import accounts, auth, budgets, categories, dashboard, export, imports, rules, search, settings as settings_router, subscriptions, transactions

settings = get_settings()

app = FastAPI(title=settings.app_name)


@app.on_event("startup")
def bootstrap_user_from_env() -> None:
    """Compatibilidad con despliegues configurados por variables de entorno (HA add-on,
    docker compose): si no existe usuario en BD pero hay credenciales en el entorno,
    se crea el perfil automáticamente y no se muestra la pantalla de registro."""
    from sqlmodel import Session, select

    from app.database import engine
    from app.models import UserProfile

    with Session(engine) as db:
        if db.exec(select(UserProfile)).first():
            return
        if settings.app_password_hash:
            db.add(
                UserProfile(
                    username=settings.app_username,
                    password_hash=settings.app_password_hash,
                    language="es",
                )
            )
            db.commit()

app.add_middleware(AuthMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, session_cookie="miney_session")

static_dir = Path(__file__).parent / "static"
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.get("/sw.js", include_in_schema=False)
def service_worker():
    # Servido desde la raíz para que su scope cubra toda la app (no solo /static)
    return FileResponse(static_dir / "sw.js", media_type="application/javascript")


app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(search.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(rules.router)
app.include_router(subscriptions.router)
app.include_router(budgets.router)
app.include_router(imports.router)
app.include_router(export.router)
app.include_router(settings_router.router)
