from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from app.database import get_db
from app.models import Category, AutoTagRule, Transaction, User
from app.schemas import CategoryCreate, CategoryUpdate, CategoryOut, AutoTagRuleCreate, AutoTagRuleOut
from app.core.dependencies import require_admin, require_editor, get_current_user

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryOut])
async def list_categories(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Category).where(Category.is_active == True).order_by(Category.sort_order, Category.name)
    )
    return result.scalars().all()


@router.post("/", response_model=CategoryOut)
async def create_category(
    data: CategoryCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    cat = Category(**data.model_dump())
    db.add(cat)
    await db.flush()
    await db.refresh(cat)
    return cat


@router.patch("/{cat_id}", response_model=CategoryOut)
async def update_category(
    cat_id: str,
    data: CategoryUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cat, field, value)
    return cat


@router.delete("/{cat_id}")
async def delete_category(
    cat_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(Category).where(Category.id == cat_id))
    cat = result.scalar_one_or_none()
    if not cat:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    # Проверяем есть ли транзакции с этой категорией
    count_result = await db.execute(
        select(func.count(Transaction.id)).where(Transaction.category_id == cat_id)
    )
    count = count_result.scalar()
    if count > 0:
        # Не удаляем, а скрываем
        cat.is_active = False
        return {"ok": True, "note": f"Категория скрыта (есть {count} транзакций)"}
    await db.delete(cat)
    return {"ok": True}


@router.get("/auto-rules", response_model=List[AutoTagRuleOut])
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AutoTagRule))
    return result.scalars().all()


@router.post("/auto-rules", response_model=AutoTagRuleOut)
async def create_rule(
    data: AutoTagRuleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    rule = AutoTagRule(**data.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.delete("/auto-rules/{rule_id}")
async def delete_rule(
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(select(AutoTagRule).where(AutoTagRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Правило не найдено")
    await db.delete(rule)
    return {"ok": True}
