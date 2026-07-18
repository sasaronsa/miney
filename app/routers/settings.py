from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.auth import get_profile
from app.database import get_session
from app.i18n import LANGUAGES, current_language, t
from app.security import hash_password, verify_password
from app.templating import templates

router = APIRouter(prefix="/settings")


@router.get("")
def settings_page(request: Request, session: Session = Depends(get_session)):
    profile = get_profile(session)
    return templates.TemplateResponse(
        "settings.html", {"request": request, "profile": profile, "languages": LANGUAGES}
    )


@router.post("/profile")
def update_profile(
    request: Request,
    username: str = Form(...),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    if profile and username.strip():
        profile.username = username.strip()
        session.add(profile)
        session.commit()
        request.session["username"] = profile.username
    return RedirectResponse(url=f"/settings?msg={t('Perfil actualizado')}", status_code=303)


@router.post("/password")
def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    password_confirm: str = Form(...),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)

    error = None
    if not profile or not verify_password(current_password, profile.password_hash):
        error = t("Contraseña actual incorrecta")
    elif new_password != password_confirm:
        error = t("Las contraseñas no coinciden")
    elif len(new_password) < 4:
        error = t("La contraseña debe tener al menos 4 caracteres")

    if error:
        return templates.TemplateResponse(
            "settings.html",
            {"request": request, "profile": profile, "languages": LANGUAGES, "password_error": error},
            status_code=400,
        )

    profile.password_hash = hash_password(new_password)
    session.add(profile)
    session.commit()
    return RedirectResponse(url=f"/settings?msg={t('Contraseña actualizada')}", status_code=303)


@router.post("/language")
def update_language(
    language: str = Form(...),
    session: Session = Depends(get_session),
):
    profile = get_profile(session)
    if profile and language in LANGUAGES:
        profile.language = language
        session.add(profile)
        session.commit()
        current_language.set(language)
    return RedirectResponse(url=f"/settings?msg={t('Idioma actualizado')}", status_code=303)
