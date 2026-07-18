from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import get_profile
from app.database import get_session
from app.i18n import LANGUAGES, current_language, t
from app.models import UserProfile
from app.security import hash_password, verify_password
from app.templating import templates

router = APIRouter()


@router.get("/setup")
def setup_form(request: Request, session: Session = Depends(get_session)):
    if get_profile(session):
        return RedirectResponse(url="/login", status_code=303)
    return templates.TemplateResponse(
        "setup.html", {"request": request, "error": None, "languages": LANGUAGES}
    )


@router.post("/setup")
def setup_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    language: str = Form("es"),
    session: Session = Depends(get_session),
):
    if get_profile(session):
        return RedirectResponse(url="/login", status_code=303)

    language = language if language in LANGUAGES else "es"
    current_language.set(language)

    error = None
    if password != password_confirm:
        error = t("Las contraseñas no coinciden")
    elif len(password) < 4:
        error = t("La contraseña debe tener al menos 4 caracteres")

    if error:
        return templates.TemplateResponse(
            "setup.html",
            {"request": request, "error": error, "languages": LANGUAGES},
            status_code=400,
        )

    profile = UserProfile(
        username=username.strip(), password_hash=hash_password(password), language=language
    )
    session.add(profile)
    session.commit()

    request.session["authenticated"] = True
    request.session["username"] = profile.username
    return RedirectResponse(url="/", status_code=303)


@router.get("/login")
def login_form(request: Request, next: str = "/"):
    return templates.TemplateResponse("login.html", {"request": request, "next": next, "error": None})


@router.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    if profile and username == profile.username and verify_password(password, profile.password_hash):
        request.session["authenticated"] = True
        request.session["username"] = profile.username
        return RedirectResponse(url=next or "/", status_code=303)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "next": next, "error": t("Usuario o contraseña incorrectos")},
        status_code=401,
    )


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
