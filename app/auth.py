from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse

from app.database import engine
from app.i18n import current_language
from app.models import UserProfile

PUBLIC_PATHS = {"/login", "/setup", "/sw.js"}
PUBLIC_PREFIXES = ("/static",)


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get("authenticated"))


def get_profile(session: Session) -> UserProfile | None:
    return session.exec(select(UserProfile)).first()


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith(PUBLIC_PREFIXES) or path == "/sw.js":
            return await call_next(request)

        with Session(engine) as session:
            profile = get_profile(session)

        current_language.set(profile.language if profile else "es")

        # Primer arranque sin usuario: todo lleva al registro
        if profile is None:
            if path != "/setup":
                return RedirectResponse(url="/setup", status_code=303)
            return await call_next(request)

        if path in PUBLIC_PATHS:
            if path == "/setup":
                return RedirectResponse(url="/login", status_code=303)
            return await call_next(request)

        if not is_authenticated(request):
            return RedirectResponse(url=f"/login?next={path}", status_code=303)

        return await call_next(request)
