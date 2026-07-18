from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select

from app.database import get_session
from app.models import Category, Transaction
from app.templating import templates

router = APIRouter(prefix="/categories")


def _build_tree(categories: list[Category]) -> list[dict]:
    by_parent: dict[int | None, list[Category]] = {}
    for c in categories:
        by_parent.setdefault(c.parent_id, []).append(c)

    def build(parent_id: int | None) -> list[dict]:
        children = sorted(by_parent.get(parent_id, []), key=lambda x: x.name)
        return [{"category": c, "children": build(c.id)} for c in children]

    return build(None)


@router.get("")
def list_categories(request: Request, session: Session = Depends(get_session)):
    categories = session.exec(select(Category)).all()
    tree = _build_tree(categories)
    return templates.TemplateResponse(
        "categories/list.html", {"request": request, "tree": tree, "categories": categories}
    )


@router.post("/new")
def create_category(
    name: str = Form(...),
    parent_id: str = Form(""),
    color: str = Form("#6366f1"),
    icon: str = Form(""),
    session: Session = Depends(get_session),
):
    category = Category(
        name=name,
        parent_id=int(parent_id) if parent_id else None,
        color=color,
        icon=icon or None,
    )
    session.add(category)
    session.commit()
    return RedirectResponse(url="/categories", status_code=303)


@router.post("/{category_id}/edit")
def update_category(
    category_id: int,
    name: str = Form(...),
    parent_id: str = Form(""),
    color: str = Form("#6366f1"),
    icon: str = Form(""),
    session: Session = Depends(get_session),
):
    category = session.get(Category, category_id)
    if category:
        category.name = name
        new_parent = int(parent_id) if parent_id else None
        category.parent_id = new_parent if new_parent != category_id else None
        category.color = color
        category.icon = icon or None
        session.add(category)
        session.commit()
    return RedirectResponse(url="/categories", status_code=303)


@router.post("/{category_id}/delete")
def delete_category(category_id: int, session: Session = Depends(get_session)):
    category = session.get(Category, category_id)
    if category:
        txs = session.exec(select(Transaction).where(Transaction.category_id == category_id)).all()
        for t in txs:
            t.category_id = None
            session.add(t)

        children = session.exec(select(Category).where(Category.parent_id == category_id)).all()
        for c in children:
            c.parent_id = None
            session.add(c)

        session.delete(category)
        session.commit()
    return RedirectResponse(url="/categories", status_code=303)
