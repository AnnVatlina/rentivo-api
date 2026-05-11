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
from app.models.property import Property
from app.models.property_transaction import PropertyTransaction
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
PROPERTY_FIELDS = [
    "id", "name", "address", "purchase_date", "purchase_price", "currency",
    "status", "sale_date", "sale_price", "sale_notes", "created_at",
]
PROPERTY_TX_FIELDS = [
    "id", "property_id", "type", "category", "title", "amount", "currency",
    "billing_cycle", "transaction_date", "start_date", "end_date", "created_at",
]


def _model_to_row(obj, fields: list[str]) -> list[str]:
    return ["" if (val := getattr(obj, f)) is None else str(val) for f in fields]


def _write_csv(fields: list[str], rows) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(fields)
    for obj in rows:
        writer.writerow(_model_to_row(obj, fields))
    return buf.getvalue()


@router.get("/export/csv")
async def export_csv(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deposits = (await db.execute(select(Deposit).where(Deposit.user_id == current_user.id))).scalars().all()
    subscriptions = (await db.execute(select(Subscription).where(Subscription.user_id == current_user.id))).scalars().all()
    properties = (await db.execute(select(Property).where(Property.user_id == current_user.id))).scalars().all()
    prop_ids = [p.id for p in properties]
    transactions = []
    if prop_ids:
        transactions = (await db.execute(
            select(PropertyTransaction).where(PropertyTransaction.property_id.in_(prop_ids))
        )).scalars().all()

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("deposits.csv", _write_csv(DEPOSIT_FIELDS, deposits))
        zf.writestr("subscriptions.csv", _write_csv(SUBSCRIPTION_FIELDS, subscriptions))
        zf.writestr("properties.csv", _write_csv(PROPERTY_FIELDS, properties))
        zf.writestr("property_transactions.csv", _write_csv(PROPERTY_TX_FIELDS, transactions))

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=rentivo_export.zip"},
    )


def _parse_date(val: str) -> date | None:
    return date.fromisoformat(val) if val else None


def _parse_decimal(val: str) -> Decimal | None:
    return Decimal(val) if val else None


def _parse_bool(val: str) -> bool:
    return val.lower() in ("true", "1", "yes")


@router.post("/import/csv", status_code=status.HTTP_200_OK)
async def import_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    created = {"deposits": 0, "subscriptions": 0, "properties": 0, "property_transactions": 0, "skipped": 0}

    archives = _unpack_zip(content) if (file.filename or "").endswith(".zip") else {file.filename or "upload.csv": content}

    for filename, data in archives.items():
        text = data.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))
        headers = reader.fieldnames or []

        if set(DEPOSIT_FIELDS).issubset(headers):
            await _import_deposits(reader, current_user.id, db, created)
        elif set(SUBSCRIPTION_FIELDS).issubset(headers):
            await _import_subscriptions(reader, current_user.id, db, created)
        elif set(PROPERTY_FIELDS).issubset(headers):
            await _import_properties(reader, current_user.id, db, created)
        elif set(PROPERTY_TX_FIELDS).issubset(headers):
            await _import_property_transactions(reader, current_user.id, db, created)
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
    rows = (await db.execute(select(Deposit.id, Deposit.source_id).where(Deposit.user_id == user_id))).all()
    seen = {str(r[0]) for r in rows} | {str(r[1]) for r in rows if r[1] is not None}

    for row in reader:
        if row["id"] in seen:
            counts["skipped"] += 1
            continue
        db.add(Deposit(
            id=uuid.uuid4(), source_id=uuid.UUID(row["id"]), user_id=user_id,
            title=row["title"], bank_name=row["bank_name"] or None,
            amount=Decimal(row["amount"]), currency=row["currency"],
            open_date=date.fromisoformat(row["open_date"]),
            close_date=_parse_date(row["close_date"]),
            annual_rate=Decimal(row["annual_rate"]),
        ))
        counts["deposits"] += 1


async def _import_subscriptions(reader, user_id: uuid.UUID, db: AsyncSession, counts: dict):
    rows = (await db.execute(select(Subscription.id, Subscription.source_id).where(Subscription.user_id == user_id))).all()
    seen = {str(r[0]) for r in rows} | {str(r[1]) for r in rows if r[1] is not None}

    for row in reader:
        if row["id"] in seen:
            counts["skipped"] += 1
            continue
        db.add(Subscription(
            id=uuid.uuid4(), source_id=uuid.UUID(row["id"]), user_id=user_id,
            title=row["title"], category=row["category"] or None,
            amount=Decimal(row["amount"]), currency=row["currency"],
            billing_cycle=row["billing_cycle"],
            start_date=date.fromisoformat(row["start_date"]),
            end_date=_parse_date(row["end_date"]),
            is_active=_parse_bool(row["is_active"]),
        ))
        counts["subscriptions"] += 1


async def _import_properties(reader, user_id: uuid.UUID, db: AsyncSession, counts: dict):
    rows = (await db.execute(
        select(Property.id, Property.source_id).where(Property.user_id == user_id)
    )).all()
    seen = {str(r[0]) for r in rows} | {str(r[1]) for r in rows if r[1] is not None}

    for row in reader:
        if row["id"] in seen:
            counts["skipped"] += 1
            continue
        db.add(Property(
            id=uuid.uuid4(), source_id=uuid.UUID(row["id"]), user_id=user_id,
            name=row["name"], address=row["address"] or None,
            purchase_date=date.fromisoformat(row["purchase_date"]),
            purchase_price=Decimal(row["purchase_price"]),
            currency=row["currency"], status=row["status"],
            sale_date=_parse_date(row["sale_date"]),
            sale_price=_parse_decimal(row["sale_price"]),
            sale_notes=row["sale_notes"] or None,
        ))
        counts["properties"] += 1


async def _import_property_transactions(reader, user_id: uuid.UUID, db: AsyncSession, counts: dict):
    # Build mapping: source_id (original export UUID) → actual property id for this user
    prop_rows = (await db.execute(
        select(Property.id, Property.source_id).where(Property.user_id == user_id)
    )).all()
    # Map CSV property_id (which is the original UUID = source_id) to the user's actual property id
    source_to_prop_id: dict[str, uuid.UUID] = {}
    direct_prop_ids: set[str] = set()
    for prop_id, source_id in prop_rows:
        direct_prop_ids.add(str(prop_id))
        if source_id is not None:
            source_to_prop_id[str(source_id)] = prop_id

    prop_id_list = [r[0] for r in prop_rows]
    existing_tx_ids = {
        str(r[0])
        for r in (await db.execute(
            select(PropertyTransaction.id).where(PropertyTransaction.property_id.in_(prop_id_list))
        )).all()
    } if prop_id_list else set()

    for row in reader:
        csv_prop_id = row["property_id"]
        # Resolve: direct match (own export) or via source_id mapping (cross-user import)
        if csv_prop_id in direct_prop_ids:
            resolved_prop_id = uuid.UUID(csv_prop_id)
        elif csv_prop_id in source_to_prop_id:
            resolved_prop_id = source_to_prop_id[csv_prop_id]
        else:
            counts["skipped"] += 1
            continue
        if row["id"] in existing_tx_ids:
            counts["skipped"] += 1
            continue
        db.add(PropertyTransaction(
            id=uuid.UUID(row["id"]),
            property_id=resolved_prop_id,
            type=row["type"], category=row["category"],
            title=row["title"], amount=Decimal(row["amount"]),
            currency=row["currency"], billing_cycle=row["billing_cycle"],
            transaction_date=_parse_date(row["transaction_date"]),
            start_date=_parse_date(row["start_date"]),
            end_date=_parse_date(row["end_date"]),
        ))
        counts["property_transactions"] += 1
