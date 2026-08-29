"""Home screen route (T0.4): hero CTA + library/groups stat cards."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Group, Meal

router = APIRouter()

templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")


@router.get("/")
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    active_meal_count = db.scalar(
        select(func.count()).select_from(Meal).where(Meal.is_active.is_(True))
    ) or 0
    active_group_count = db.scalar(
        select(func.count()).select_from(Group)
    ) or 0
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "active_meal_count": active_meal_count,
            "active_group_count": active_group_count,
        },
    )
