import uuid
from datetime import date
from decimal import Decimal
from dateutil.relativedelta import relativedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deposit import Deposit
from app.models.property import Property
from app.models.property_transaction import PropertyTransaction
from app.models.subscription import Subscription


async def seed_demo_data(user_id: uuid.UUID, db: AsyncSession) -> dict:
    today = date.today()
    counts = {"deposits": 0, "subscriptions": 0, "properties": 0, "property_transactions": 0}

    # ── Deposits ──────────────────────────────────────────────────────────────
    deposits = [
        Deposit(
            id=uuid.uuid4(), user_id=user_id,
            title="Bank of America — Savings",
            bank_name="Bank of America",
            amount=Decimal("15000.00"), currency="USD",
            open_date=today - relativedelta(months=10),
            close_date=today + relativedelta(days=12),
            annual_rate=Decimal("4.80"),
            interest_type="simple",
        ),
        Deposit(
            id=uuid.uuid4(), user_id=user_id,
            title="Chase — High-Yield",
            bank_name="Chase",
            amount=Decimal("8000.00"), currency="USD",
            open_date=today - relativedelta(months=8),
            close_date=None,
            annual_rate=Decimal("5.10"),
            interest_type="compound", compound_frequency="monthly",
        ),
        Deposit(
            id=uuid.uuid4(), user_id=user_id,
            title="Marcus — Fixed Term",
            bank_name="Marcus by Goldman Sachs",
            amount=Decimal("20000.00"), currency="USD",
            open_date=today - relativedelta(months=3),
            close_date=today + relativedelta(months=9),
            annual_rate=Decimal("5.30"),
            interest_type="simple",
        ),
        Deposit(
            id=uuid.uuid4(), user_id=user_id,
            title="Wells Fargo — Short Term",
            bank_name="Wells Fargo",
            amount=Decimal("5000.00"), currency="USD",
            open_date=today - relativedelta(months=8),
            close_date=today - relativedelta(months=2),
            annual_rate=Decimal("4.50"),
            interest_type="simple",
        ),
    ]
    for d in deposits:
        db.add(d)
    counts["deposits"] = len(deposits)

    # ── Subscriptions ─────────────────────────────────────────────────────────
    subs = [
        Subscription(
            id=uuid.uuid4(), user_id=user_id,
            title="Netflix", category="Streaming",
            amount=Decimal("15.99"), currency="USD",
            billing_cycle="monthly",
            start_date=today - relativedelta(years=2),
            is_active=True,
        ),
        Subscription(
            id=uuid.uuid4(), user_id=user_id,
            title="Spotify Family", category="Music",
            amount=Decimal("14.99"), currency="USD",
            billing_cycle="monthly",
            start_date=today - relativedelta(months=18),
            is_active=True,
        ),
        Subscription(
            id=uuid.uuid4(), user_id=user_id,
            title="iCloud 200 GB", category="Cloud",
            amount=Decimal("2.99"), currency="USD",
            billing_cycle="monthly",
            start_date=today - relativedelta(years=3),
            is_active=True,
        ),
        Subscription(
            id=uuid.uuid4(), user_id=user_id,
            title="Gym membership", category="Sport",
            amount=Decimal("49.00"), currency="USD",
            billing_cycle="monthly",
            start_date=today - relativedelta(months=6),
            is_active=True,
        ),
        Subscription(
            id=uuid.uuid4(), user_id=user_id,
            title="Adobe Creative Cloud", category="Work",
            amount=Decimal("54.99"), currency="USD",
            billing_cycle="monthly",
            start_date=today - relativedelta(months=24),
            is_active=False,
        ),
        Subscription(
            id=uuid.uuid4(), user_id=user_id,
            title="ChatGPT Plus", category="AI",
            amount=Decimal("20.00"), currency="USD",
            billing_cycle="monthly",
            start_date=today - relativedelta(months=8),
            is_active=True,
        ),
    ]
    for s in subs:
        db.add(s)
    counts["subscriptions"] = len(subs)

    # ── Property ──────────────────────────────────────────────────────────────
    prop = Property(
        id=uuid.uuid4(), user_id=user_id,
        name="Apartment, Tbilisi",
        address="Rustaveli Ave, 15, apt. 8",
        purchase_date=today - relativedelta(years=3),
        purchase_price=Decimal("120000.00"),
        currency="USD",
        status="active",
    )
    db.add(prop)
    counts["properties"] = 1

    rent_start = today - relativedelta(years=2, months=6)
    transactions = [
        PropertyTransaction(
            id=uuid.uuid4(), property_id=prop.id,
            type="income", category="Rent",
            title="Monthly rent",
            amount=Decimal("1500.00"), currency="GEL",
            billing_cycle="monthly",
            start_date=rent_start,
        ),
        PropertyTransaction(
            id=uuid.uuid4(), property_id=prop.id,
            type="expense", category="Management",
            title="Property management fee",
            amount=Decimal("150.00"), currency="GEL",
            billing_cycle="monthly",
            start_date=rent_start,
        ),
        PropertyTransaction(
            id=uuid.uuid4(), property_id=prop.id,
            type="expense", category="Renovation",
            title="Apartment renovation",
            amount=Decimal("18000.00"), currency="GEL",
            billing_cycle="one_time",
            transaction_date=today - relativedelta(years=2, months=8),
        ),
        PropertyTransaction(
            id=uuid.uuid4(), property_id=prop.id,
            type="expense", category="Furniture",
            title="Furniture & appliances",
            amount=Decimal("9500.00"), currency="GEL",
            billing_cycle="one_time",
            transaction_date=today - relativedelta(years=2, months=7),
        ),
    ]
    for tx in transactions:
        db.add(tx)
    counts["property_transactions"] = len(transactions)

    await db.commit()
    return counts


async def clear_all_data(user_id: uuid.UUID, db: AsyncSession) -> dict:
    from sqlalchemy import delete, select
    from app.models.property_transaction import PropertyTransaction

    prop_ids = (
        await db.execute(
            select(Property.id).where(Property.user_id == user_id)
        )
    ).scalars().all()

    if prop_ids:
        await db.execute(
            delete(PropertyTransaction).where(PropertyTransaction.property_id.in_(prop_ids))
        )

    results = {}
    for Model, key in [
        (Property, "properties"),
        (Deposit, "deposits"),
        (Subscription, "subscriptions"),
    ]:
        r = await db.execute(
            delete(Model).where(Model.user_id == user_id)
        )
        results[key] = r.rowcount

    await db.commit()
    return results
