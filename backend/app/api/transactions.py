from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func, extract
from typing import List, Optional
from datetime import date, timedelta
import aiofiles
import os
import uuid

from app.database import get_db
from app.models import Transaction, TransactionType, Category, AutoTagRule, AuditLog, User
from app.schemas import TransactionCreate, TransactionUpdate, TransactionOut
from app.core.dependencies import require_editor, get_current_user
from app.config import settings

router = APIRouter(prefix="/transactions", tags=["transactions"])


async def auto_detect_category(description: str, db: AsyncSession) -> Optional[str]:
    """Автоматически определить категорию по ключевым словам"""
    if not description:
        return None
    text = description.lower()
    result = await db.execute(select(AutoTagRule))
    rules = result.scalars().all()
    for rule in rules:
        if rule.keyword.lower() in text:
            return rule.category_id
    return None


@router.get("/", response_model=List[TransactionOut])
async def list_transactions(
    type: Optional[TransactionType] = None,
    category_id: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Transaction)
    filters = []
    if type:
        filters.append(Transaction.type == type)
    if category_id:
        filters.append(Transaction.category_id == category_id)
    if date_from:
        filters.append(Transaction.date >= date_from)
    if date_to:
        filters.append(Transaction.date <= date_to)
    if search:
        filters.append(Transaction.description.ilike(f"%{search}%"))
    if filters:
        q = q.where(and_(*filters))
    q = q.order_by(Transaction.date.desc(), Transaction.created_at.desc()).offset(skip).limit(limit)

    result = await db.execute(q)
    transactions = result.scalars().all()

    out = []
    for t in transactions:
        t_dict = {
            "id": t.id, "type": t.type, "amount": t.amount, "date": t.date,
            "category_id": t.category_id, "category": None,
            "description": t.description, "receipt_url": t.receipt_url,
            "receipt_file": t.receipt_file, "is_historical": t.is_historical,
            "created_at": t.created_at,
        }
        if t.category_id:
            cat_res = await db.execute(select(Category).where(Category.id == t.category_id))
            cat = cat_res.scalar_one_or_none()
            if cat:
                t_dict["category"] = {"id": cat.id, "name": cat.name, "color": cat.color,
                                       "icon": cat.icon, "is_active": cat.is_active, "sort_order": cat.sort_order}
        out.append(TransactionOut.model_validate(t_dict))
    return out


@router.post("/", response_model=TransactionOut)
async def create_transaction(
    data: TransactionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    category_id = data.category_id
    if not category_id and data.description:
        category_id = await auto_detect_category(data.description, db)

    t = Transaction(
        type=data.type,
        amount=data.amount,
        date=data.date,
        category_id=category_id,
        description=data.description,
        receipt_url=data.receipt_url,
        is_historical=data.is_historical,
        created_by=current_user.id,
    )
    db.add(t)
    await db.flush()
    db.add(AuditLog(
        user_id=current_user.id,
        action="create",
        entity="transaction",
        entity_id=t.id,
        new_data={"type": str(t.type), "amount": t.amount, "date": str(t.date)},
    ))
    await db.refresh(t)
    return TransactionOut.model_validate({
        "id": t.id, "type": t.type, "amount": t.amount, "date": t.date,
        "category_id": t.category_id, "category": None,
        "description": t.description, "receipt_url": t.receipt_url,
        "receipt_file": t.receipt_file, "is_historical": t.is_historical,
        "created_at": t.created_at,
    })


@router.get("/{t_id}", response_model=TransactionOut)
async def get_transaction(
    t_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    result = await db.execute(select(Transaction).where(Transaction.id == t_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    return TransactionOut.model_validate({
        "id": t.id, "type": t.type, "amount": t.amount, "date": t.date,
        "category_id": t.category_id, "category": None,
        "description": t.description, "receipt_url": t.receipt_url,
        "receipt_file": t.receipt_file, "is_historical": t.is_historical,
        "created_at": t.created_at,
    })


@router.patch("/{t_id}", response_model=TransactionOut)
async def update_transaction(
    t_id: str,
    data: TransactionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    result = await db.execute(select(Transaction).where(Transaction.id == t_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")

    old = {"amount": t.amount, "date": str(t.date), "category_id": t.category_id}
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(t, field, value)

    db.add(AuditLog(
        user_id=current_user.id,
        action="update",
        entity="transaction",
        entity_id=t_id,
        old_data=old,
        new_data=data.model_dump(exclude_none=True),
    ))
    return TransactionOut.model_validate({
        "id": t.id, "type": t.type, "amount": t.amount, "date": t.date,
        "category_id": t.category_id, "category": None,
        "description": t.description, "receipt_url": t.receipt_url,
        "receipt_file": t.receipt_file, "is_historical": t.is_historical,
        "created_at": t.created_at,
    })


@router.delete("/{t_id}")
async def delete_transaction(
    t_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    result = await db.execute(select(Transaction).where(Transaction.id == t_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    old = {"amount": t.amount, "date": str(t.date), "type": str(t.type)}
    await db.delete(t)
    db.add(AuditLog(
        user_id=current_user.id,
        action="delete",
        entity="transaction",
        entity_id=t_id,
        old_data=old,
    ))
    return {"ok": True}


@router.post("/{t_id}/receipt")
async def upload_receipt(
    t_id: str,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_editor),
):
    result = await db.execute(select(Transaction).where(Transaction.id == t_id))
    t = result.scalar_one_or_none()
    if not t:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")

    ext = os.path.splitext(file.filename)[1] if file.filename else ".file"
    filename = f"{uuid.uuid4()}{ext}"
    upload_path = os.path.join(settings.UPLOAD_DIR, filename)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    async with aiofiles.open(upload_path, "wb") as f:
        content = await file.read()
        await f.write(content)

    t.receipt_file = filename
    return {"filename": filename, "url": f"/uploads/{filename}"}


@router.get("/summary/by-month")
async def summary_by_month(
    year: int = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    from datetime import datetime
    if not year:
        year = datetime.now().year

    result = await db.execute(
        select(
            extract("month", Transaction.date).label("month"),
            Transaction.type,
            func.sum(Transaction.amount).label("total"),
        )
        .where(extract("year", Transaction.date) == year)
        .group_by("month", Transaction.type)
        .order_by("month")
    )
    rows = result.all()

    months = {}
    for row in rows:
        m = int(row.month)
        if m not in months:
            months[m] = {"month": m, "income": 0.0, "expense": 0.0}
        if row.type == TransactionType.income:
            months[m]["income"] = float(row.total)
        else:
            months[m]["expense"] = float(row.total)

    for m in months.values():
        m["profit"] = m["income"] - m["expense"]

    return list(months.values())
