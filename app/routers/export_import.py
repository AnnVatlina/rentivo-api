import csv
import io
import uuid
import zipfile
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.deposit import Deposit
from app.models.subscription import Subscription
from app.models.user import User

router = APIRouter(dependencies=[Depends(get_current_user)])

DEPOSIT_FIELDS = [
    "id", "title", "bank_name", "amount", "currency",
    "open_date", "close_date", "annual_rate", "created_at",
]
SUBSCRIPTION_FIELDS = [
    "id", "title", "category", "amount", "currency",
    "billing_cycle", "start_date", "end_date", "is_active", "created_at",
]


def _model_to_row(obj, fields: list[str]) -> list[str]:
    row = []
    for f in fields:
        val = getattr(obj, f)
        row.append("" if val is None else str(val))
    return row


@router.get("/export/csv")
async def export_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposits = (
        await db.execute(select(Deposit).where(Deposit.user_id == current_user.id))
    ).scalars().all()

    subscriptions = (
        await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))
    ).scalars().all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, fields, rows in [
            ("deposits.csv", DEPOSIT_FIELDS, deposits),
            ("subscriptions.csv", SUBSCRIPTION_FIELDS, subscriptions),
        ]:
            csv_buf = io.StringIO()
            writer = csv.writer(csv_buf)
            writer.writerow(fields)
            for obj in rows:
                writer.writerow(_model_to_row(obj, fields))
            zf.writestr(name, csv_buf.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=rentivo_export.zip"},
    )


def _parse_date(val: str) -> date | None:
    return date.fromisoformat(val) if val else None


def _parse_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "yes")


@router.post("/import/csv", status_code=status.HTTP_200_OK)
async def import_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    created = {"deposits": 0, "subscriptions": 0, "skipped": 0}

    if file.filename and file.filename.endswith(".zip"):
        archives = _unpack_zip(content)
    else:
        archives = {file.filename or "upload.csv": content}

    for filename, data in archives.items():
        text = data.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []

        if set(DEPOSIT_FIELDS).issubset(headers):
            await _import_deposits(reader, current_user.id, db, created)
        elif set(SUBSCRIPTION_FIELDS).issubset(headers):
            await _import_subscriptions(reader, current_user.id, db, created)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unrecognized CSV format in {filename}",
            )

    await db.commit()
    return created


def _unpack_zip(content: bytes) -> dict[str, bytes]:
    buf = io.BytesIO(content)
    result = {}
    with zipfile.ZipFile(buf) as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                result[name] = zf.read(name)
    return result


async def _import_deposits(reader, user_id: uuid.UUID, db: AsyncSession, counts: dict):
    rows = (await db.execute(
        select(Deposit.id, Deposit.source_id).where(Deposit.user_id == user_id)
    )).all()
    seen = {str(r[0]) for r in rows} | {str(r[1]) for r in rows if r[1] is not None}

    for row in reader:
        if row["id"] in seen:
            counts["skipped"] += 1
            continue
        dep = Deposit(
            id=uuid.uuid4(),
            source_id=uuid.UUID(row["id"]),
            user_id=user_id,
            title=row["title"],
            bank_name=row["bank_name"] or None,
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            open_date=date.fromisoformat(row["open_date"]),
            close_date=_parse_date(row["close_date"]),
            annual_rate=Decimal(row["annual_rate"]),
        )
        db.add(dep)
        counts["deposits"] += 1


async def _import_subscriptions(reader, user_id: uuid.UUID, db: AsyncSession, counts: dict):
    rows = (await db.execute(
        select(Subscription.id, Subscription.source_id).where(Subscription.user_id == user_id)
    )).all()
    seen = {str(r[0]) for r in rows} | {str(r[1]) for r in rows if r[1] is not None}

    for row in reader:
        if row["id"] in seen:
            counts["skipped"] += 1
            continue
        sub = Subscription(
            id=uuid.uuid4(),
            source_id=uuid.UUID(row["id"]),
            user_id=user_id,
            title=row["title"],
            category=row["category"] or None,
            amount=Decimal(row["amount"]),
            currency=row["currency"],
            billing_cycle=row["billing_cycle"],
            start_date=date.fromisoformat(row["start_date"]),
            end_date=_parse_date(row["end_date"]),
            is_active=_parse_bool(row["is_active"]),
        )
        db.add(sub)
        counts["subscriptions"] += 1
