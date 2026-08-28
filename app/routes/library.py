"""Meal library routes (M2, T2.1–T2.2): browse/search/filter, create, edit,
archive/unarchive, type cycle, and the recipe view.

The library list and the recipe view are public — the household reaches them
from any device. Create/edit/archive/cycle-type are admin-only (D16), gated
server-side by ``require_admin``.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.auth import get_current_person, require_admin
from app.db import get_db
from app.models import Meal, MealTag, Tag

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")

TYPE_LABELS = {"dinner": "Dinner", "lunch": "Lunch", "both": "Both"}
TYPE_HUES = {"dinner": 25, "lunch": 140, "both": 300}
TYPE_CYCLE = {"dinner": "lunch", "lunch": "both", "both": "dinner"}
VALID_TYPES = frozenset(TYPE_LABELS)


def _normalize_name(name: str) -> str:
    """D11 dedupe key, shared with scripts/seed.py: casefold + collapse."""
    return re.sub(r"\s+", " ", name.casefold()).strip()


def _type_pill_style(meal_type: str, interactive: bool = False) -> str:
    hue = TYPE_HUES[meal_type]
    cursor = "cursor:pointer;" if interactive else ""
    return (
        f"flex:none;border:none;border-radius:999px;padding:6px 10px;"
        f"font:700 10.5px var(--dd-font-body);{cursor}"
        f"background:oklch(0.92 0.05 {hue});color:oklch(0.4 0.1 {hue});"
    )


def _get_meal_or_404(db: Session, meal_id: int) -> Meal:
    meal = db.get(Meal, meal_id)
    if meal is None:
        raise HTTPException(404, "No such meal")
    return meal


def _meal_tags(db: Session, meal_id: int) -> list[str]:
    return list(
        db.scalars(
            select(Tag.name)
            .join(MealTag, MealTag.tag_id == Tag.id)
            .where(MealTag.meal_id == meal_id)
            .order_by(Tag.name)
        ).all()
    )


def _has_recipe(meal: Meal) -> bool:
    return bool(meal.source_url or meal.recipe_text or (meal.ingredients or "").strip())


def _safe_source_url(url: str | None) -> str | None:
    """Return url only when it is an absolute http(s) URL with a host, else None."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return url


def _all_tags(db: Session) -> list[Tag]:
    return list(db.scalars(select(Tag).order_by(Tag.name)).all())


def _render_edit(
    request: Request,
    db: Session,
    meal: Meal | None,
    form: dict,
    selected_tags: list[str],
    error: str | None,
    status_code: int = 200,
):
    """Render meal_edit.html for a new (meal=None) or existing meal.

    ``form`` holds the current field values (name/type/ingredients/
    instructions/source_url) — from the meal for GETs, from the submitted
    POST body for 400 re-renders so nothing the user typed is lost.
    """
    meal_type = form["type"] if form["type"] in VALID_TYPES else "dinner"
    hue = TYPE_HUES[meal_type]
    return templates.TemplateResponse(
        request,
        "meal_edit.html",
        {
            "meal": meal,
            "form": form,
            "selected_tags": selected_tags,
            "all_tags": _all_tags(db),
            "error": error,
            "track_label": TYPE_LABELS[meal_type],
            "track_style": (
                f"border:none;border-radius:999px;padding:9px 16px;margin-top:6px;"
                f"font:700 12px var(--dd-font-body);cursor:pointer;"
                f"background:oklch(0.92 0.05 {hue});color:oklch(0.4 0.1 {hue});"
            ),
        },
        status_code=status_code,
    )


def _empty_form(type: str = "dinner") -> dict:
    return {
        "name": "",
        "type": type if type in VALID_TYPES else "dinner",
        "ingredients": "",
        "instructions": "",
        "source_url": "",
    }


def _meal_form(meal: Meal) -> dict:
    return {
        "name": meal.name,
        "type": meal.type,
        "ingredients": meal.ingredients or "",
        "instructions": meal.recipe_text or "",
        "source_url": meal.source_url or "",
    }


def _clean_form(
    name: str, type: str, ingredients: str, instructions: str, source_url: str
) -> dict:
    """Whitespace rules from the M2 spec: ingredients lose only trailing blank
    lines (internal blank lines are preserved); instructions lose trailing
    whitespace; name/source_url are trimmed."""
    return {
        "name": name.strip(),
        "type": type,
        "ingredients": ingredients.rstrip("\r\n"),
        "instructions": instructions.rstrip(),
        "source_url": source_url.strip(),
    }


def _resolve_tags(db: Session, raw_tags: list[str]) -> list[Tag]:
    """Create any missing tags (household tags are freely created) and return
    the Tag rows in submitted order, deduped by name."""
    tags: list[Tag] = []
    seen: set[str] = set()
    for raw in raw_tags:
        name = raw.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        tag = db.scalar(select(Tag).where(Tag.name == name))
        if tag is None:
            tag = Tag(name=name)
            db.add(tag)
            db.flush()
        tags.append(tag)
    return tags


def _validate_form(form: dict, db: Session, exclude_meal_id: int | None = None) -> str | None:
    """Return an error message, or None when the form is valid."""
    if not form["name"]:
        return "Name is required."
    if form["type"] not in VALID_TYPES:
        return "Type must be dinner, lunch, or both."
    if form["source_url"] and _safe_source_url(form["source_url"]) is None:
        return "Source URL must start with http:// or https://."
    normalized = _normalize_name(form["name"])
    collision = select(Meal.id).where(Meal.normalized_name == normalized)
    if exclude_meal_id is not None:
        collision = collision.where(Meal.id != exclude_meal_id)
    if db.scalar(collision) is not None:
        return "A meal with that name already exists."
    return None


@router.get("/library")
def library_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    q: str = "",
    type: str = "",
    tags: str = "",
    status: str = "active",
):
    """Public library browse: search (q), type / tag (OR) / status filters."""
    current = get_current_person(request, db)
    can_edit = current is not None and current.is_admin

    type = type if type in VALID_TYPES else ""
    status = status if status in ("active", "archived", "all") else "active"
    tag_names = [t.strip() for t in tags.split(",") if t.strip()]

    stmt = select(Meal)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Meal.name.ilike(like) | Meal.normalized_name.ilike(like))
    if type:
        stmt = stmt.where(Meal.type == type)
    if tag_names:
        meal_ids = db.scalars(
            select(MealTag.meal_id)
            .join(Tag, Tag.id == MealTag.tag_id)
            .where(Tag.name.in_(tag_names))
            .distinct()
        ).all()
        stmt = stmt.where(Meal.id.in_(meal_ids))
    if status == "active":
        stmt = stmt.where(Meal.archived_at.is_(None))
    elif status == "archived":
        stmt = stmt.where(Meal.archived_at.is_not(None))
    meals = db.scalars(stmt.order_by(Meal.name)).all()

    meal_tags = db.execute(
        select(MealTag.meal_id, Tag.name).join(Tag, Tag.id == MealTag.tag_id)
    ).all()
    tags_by_meal: dict[int, list[str]] = defaultdict(list)
    for meal_id, tag_name in meal_tags:
        tags_by_meal[meal_id].append(tag_name)

    rows = [
        {
            "id": meal.id,
            "name": meal.name,
            "type_label": TYPE_LABELS[meal.type],
            "type_style": _type_pill_style(meal.type, interactive=can_edit),
            "tags": sorted(tags_by_meal.get(meal.id, [])),
            "kept_label": f"Kept {meal.times_kept}×" if meal.times_kept > 0 else None,
            "has_recipe": _has_recipe(meal),
            "archived": meal.archived_at is not None,
        }
        for meal in meals
    ]

    active_count = (
        db.scalar(
            select(func.count()).select_from(Meal).where(Meal.archived_at.is_(None))
        )
        or 0
    )
    archived_count = (
        db.scalar(
            select(func.count()).select_from(Meal).where(Meal.archived_at.is_not(None))
        )
        or 0
    )

    def _filter_url(overrides: dict) -> str:
        params = {"q": q, "type": type, "tags": tags, "status": status}
        params.update({k: v for k, v in overrides.items() if v is not None})
        params = {k: v for k, v in params.items() if v}
        return f"/library?{urlencode(params)}" if params else "/library"

    def _toggle_tag_url(tag_name: str) -> str:
        if tag_name in tag_names:
            new_tags = [t for t in tag_names if t != tag_name]
        else:
            new_tags = tag_names + [tag_name]
        return _filter_url({"tags": ",".join(new_tags)})

    type_filters = [
        {
            "label": "All" if key == "all" else TYPE_LABELS[key],
            "value": "" if key == "all" else key,
            "active": type == ("" if key == "all" else key),
        }
        for key in ("all", "dinner", "lunch", "both")
    ]
    status_filters = [
        {"label": label, "value": value, "active": status == value}
        for label, value in (("Active", "active"), ("Archived", "archived"), ("All", "all"))
    ]
    tag_filters = [
        {
            "name": tag.name,
            "url": _toggle_tag_url(tag.name),
            "selected": tag.name in tag_names,
        }
        for tag in _all_tags(db)
    ]

    return templates.TemplateResponse(
        request,
        "library.html",
        {
            "meals": rows,
            "active_count": active_count,
            "archived_count": archived_count,
            "can_edit": can_edit,
            "q": q,
            "type": type,
            "tags": tags,
            "status": status,
            "type_filters": type_filters,
            "status_filters": status_filters,
            "tag_filters": tag_filters,
        },
    )


@router.get("/library/new")
def new_meal_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    type: str = "dinner",
):
    """Blank edit page for a new meal (admin-only). ``?type=`` presets the
    track; the in-form cycle button drives it from there."""
    require_admin(request, db)
    return _render_edit(
        request, db, None, _empty_form(type), [], error=None
    )


@router.get("/library/{meal_id}")
def recipe_view(
    request: Request, meal_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Public recipe view: name, type/tags, ingredients (bulleted), then
    instructions, then the optional original-source link."""
    meal = _get_meal_or_404(db, meal_id)
    ingredients = [
        line.strip()
        for line in (meal.ingredients or "").splitlines()
        if line.strip()
    ]
    return templates.TemplateResponse(
        request,
        "recipe.html",
        {
            "meal": meal,
            "tags": _meal_tags(db, meal.id),
            "type_label": TYPE_LABELS[meal.type],
            "type_style": _type_pill_style(meal.type),
            "ingredients": ingredients,
            "safe_source_url": _safe_source_url(meal.source_url),
        },
    )


@router.get("/library/{meal_id}/edit")
def edit_meal_page(
    request: Request, meal_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Edit page for an existing meal (admin-only)."""
    require_admin(request, db)
    meal = _get_meal_or_404(db, meal_id)
    return _render_edit(
        request, db, meal, _meal_form(meal), _meal_tags(db, meal.id), error=None
    )


@router.post("/library")
def create_meal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: Annotated[str, Form()],
    type: Annotated[str, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
):
    """Create a meal (admin-only). 303 to the new meal's edit page."""
    require_admin(request, db)
    tags = tags or []
    form = _clean_form(name, type, ingredients, instructions, source_url)
    error = _validate_form(form, db)
    if error is not None:
        return _render_edit(
            request, db, None, form, _tag_names(tags), error, status_code=400
        )
    meal = Meal(
        name=form["name"],
        normalized_name=_normalize_name(form["name"]),
        type=form["type"],
        ingredients=form["ingredients"] or None,
        recipe_text=form["instructions"] or None,
        source_url=_safe_source_url(form["source_url"]) or None,
        is_active=True,
    )
    db.add(meal)
    db.flush()
    for tag in _resolve_tags(db, tags):
        db.add(MealTag(meal_id=meal.id, tag_id=tag.id))
    db.commit()
    return RedirectResponse(f"/library/{meal.id}/edit", status_code=303)


@router.post("/library/{meal_id}")
def update_meal(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    meal_id: int,
    name: Annotated[str, Form()],
    type: Annotated[str, Form()],
    tags: Annotated[list[str] | None, Form()] = None,
    ingredients: Annotated[str, Form()] = "",
    instructions: Annotated[str, Form()] = "",
    source_url: Annotated[str, Form()] = "",
):
    """Update a meal (admin-only): rename recomputes normalized_name; the
    collision check excludes this meal itself."""
    require_admin(request, db)
    tags = tags or []
    meal = _get_meal_or_404(db, meal_id)
    form = _clean_form(name, type, ingredients, instructions, source_url)
    error = _validate_form(form, db, exclude_meal_id=meal.id)
    if error is not None:
        return _render_edit(
            request, db, meal, form, _tag_names(tags), error, status_code=400
        )
    meal.name = form["name"]
    meal.normalized_name = _normalize_name(form["name"])
    meal.type = form["type"]
    meal.ingredients = form["ingredients"] or None
    meal.recipe_text = form["instructions"] or None
    meal.source_url = _safe_source_url(form["source_url"]) or None
    db.execute(delete(MealTag).where(MealTag.meal_id == meal.id))
    for tag in _resolve_tags(db, tags):
        db.add(MealTag(meal_id=meal.id, tag_id=tag.id))
    db.commit()
    return RedirectResponse(f"/library/{meal.id}/edit", status_code=303)


@router.post("/library/{meal_id}/archive")
def archive_meal(
    request: Request, meal_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Archive (admin-only, reversible — never deleted, D16)."""
    require_admin(request, db)
    meal = _get_meal_or_404(db, meal_id)
    meal.archived_at = func.now()
    db.commit()
    return RedirectResponse("/library", status_code=303)


@router.post("/library/{meal_id}/unarchive")
def unarchive_meal(
    request: Request, meal_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Restore an archived meal (admin-only)."""
    require_admin(request, db)
    meal = _get_meal_or_404(db, meal_id)
    meal.archived_at = None
    db.commit()
    return RedirectResponse("/library", status_code=303)


@router.post("/library/{meal_id}/cycle-type")
def cycle_type(
    request: Request, meal_id: int, db: Annotated[Session, Depends(get_db)]
):
    """Type cycle dinner → lunch → both → dinner (admin-only)."""
    require_admin(request, db)
    meal = _get_meal_or_404(db, meal_id)
    meal.type = TYPE_CYCLE[meal.type]
    db.commit()
    return RedirectResponse("/library", status_code=303)


def _tag_names(raw_tags: list[str]) -> list[str]:
    """Dedupe + strip submitted tag names for re-render (create/update 400s)."""
    seen: set[str] = set()
    names: list[str] = []
    for raw in raw_tags:
        name = raw.strip()
        if name and name not in seen:
            seen.add(name)
            names.append(name)
    return names
