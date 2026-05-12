from datetime import date
from decimal import Decimal

from app.models.property import Property
from app.models.property_transaction import PropertyTransaction

_CYCLE_N = {"weekly": Decimal("52") / 12, "monthly": Decimal("1"),
            "quarterly": Decimal("1") / 3, "yearly": Decimal("1") / 12}


def _monthly_amount(tx: PropertyTransaction) -> Decimal:
    if tx.billing_cycle == "one_time":
        return tx.amount
    return tx.amount * _CYCLE_N.get(tx.billing_cycle, Decimal("1"))


def _tx_active_in_month(tx: PropertyTransaction, year: int, month: int) -> bool:
    month_start = date(year, month, 1)
    month_end = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)

    if tx.billing_cycle == "one_time":
        return tx.transaction_date is not None and month_start <= tx.transaction_date < month_end

    if tx.start_date is None or tx.start_date >= month_end:
        return False
    if tx.end_date is not None and tx.end_date < month_start:
        return False
    return True


def monthly_cashflow(
    transactions: list[PropertyTransaction],
    year: int,
    month: int,
    currency: str,  # noqa: ARG001 — kept for signature compat, conversion is done on frontend
) -> dict:
    income = Decimal("0")
    expenses = Decimal("0")
    for tx in transactions:
        if not _tx_active_in_month(tx, year, month):
            continue
        amount = _monthly_amount(tx)
        if tx.type == "income":
            income += amount
        else:
            expenses += amount
    return {"income": income, "expenses": expenses, "net": income - expenses}


def total_summary(prop: Property, transactions: list[PropertyTransaction]) -> dict:
    one_time_expenses = sum(
        tx.amount for tx in transactions
        if tx.type == "expense" and tx.billing_cycle == "one_time" and tx.currency == prop.currency
    )
    total_invested = prop.purchase_price + one_time_expenses
    total_income = sum(
        tx.amount for tx in transactions
        if tx.type == "income" and tx.currency == prop.currency
    )
    total_expenses = sum(
        tx.amount for tx in transactions
        if tx.type == "expense" and tx.currency == prop.currency
    )
    profit = None
    if prop.status == "sold" and prop.sale_price is not None:
        profit = prop.sale_price - total_invested + total_income

    return {
        "total_invested": total_invested,
        "total_income": total_income,
        "total_expenses": total_expenses,
        "profit": profit,
    }
