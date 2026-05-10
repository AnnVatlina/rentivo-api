"""Integration tests for GET /export/csv and POST /import/csv."""
import csv
import io
import uuid
import zipfile

import pytest
from httpx import AsyncClient

# ── Helpers ───────────────────────────────────────────────────────────────────

DEPOSIT = {
    "title": "Export deposit",
    "bank_name": "Sberbank",
    "amount": "50000.00",
    "currency": "USD",
    "open_date": "2026-01-01",
    "close_date": "2026-12-31",
    "annual_rate": "5.0",
}

SUBSCRIPTION = {
    "title": "Export sub",
    "category": "Tools",
    "amount": "9.99",
    "currency": "USD",
    "billing_cycle": "monthly",
    "start_date": "2026-01-01",
    "is_active": True,
}


def _open_zip(content: bytes) -> dict[str, str]:
    buf = io.BytesIO(content)
    with zipfile.ZipFile(buf) as zf:
        return {name: zf.read(name).decode() for name in zf.namelist()}


def _csv_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


# ── Auth guard ────────────────────────────────────────────────────────────────

async def test_export_requires_auth(client: AsyncClient):
    assert (await client.get("/export/csv")).status_code == 403


async def test_import_requires_auth(client: AsyncClient):
    assert (await client.post("/import/csv", files={"file": ("f.csv", b"", "text/csv")})).status_code == 403


# ── Export ────────────────────────────────────────────────────────────────────

async def test_export_empty_returns_valid_zip(client: AsyncClient, auth: dict):
    resp = await client.get("/export/csv", headers=auth["headers"])
    assert resp.status_code == 200
    assert "application/zip" in resp.headers["content-type"]
    files = _open_zip(resp.content)
    assert "deposits.csv" in files
    assert "subscriptions.csv" in files
    # Only header row — no data rows
    assert len(_csv_rows(files["deposits.csv"])) == 0
    assert len(_csv_rows(files["subscriptions.csv"])) == 0


async def test_export_deposits_csv_headers(client: AsyncClient, auth: dict):
    await client.post("/deposits", json=DEPOSIT, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=auth["headers"])
    files = _open_zip(resp.content)
    reader = csv.reader(io.StringIO(files["deposits.csv"]))
    headers = next(reader)
    expected = ["id", "title", "bank_name", "amount", "currency",
                "open_date", "close_date", "annual_rate", "created_at"]
    assert headers == expected


async def test_export_subscriptions_csv_headers(client: AsyncClient, auth: dict):
    await client.post("/subscriptions", json=SUBSCRIPTION, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=auth["headers"])
    files = _open_zip(resp.content)
    reader = csv.reader(io.StringIO(files["subscriptions.csv"]))
    headers = next(reader)
    expected = ["id", "title", "category", "amount", "currency",
                "billing_cycle", "start_date", "end_date", "is_active", "created_at"]
    assert headers == expected


async def test_export_contains_deposit_data(client: AsyncClient, auth: dict):
    await client.post("/deposits", json=DEPOSIT, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=auth["headers"])
    files = _open_zip(resp.content)
    rows = _csv_rows(files["deposits.csv"])
    assert len(rows) == 1
    assert rows[0]["title"] == "Export deposit"
    assert rows[0]["bank_name"] == "Sberbank"
    assert rows[0]["currency"] == "USD"
    assert rows[0]["annual_rate"] == "5.0000"


async def test_export_contains_subscription_data(client: AsyncClient, auth: dict):
    await client.post("/subscriptions", json=SUBSCRIPTION, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=auth["headers"])
    files = _open_zip(resp.content)
    rows = _csv_rows(files["subscriptions.csv"])
    assert len(rows) == 1
    assert rows[0]["title"] == "Export sub"
    assert rows[0]["billing_cycle"] == "monthly"
    assert rows[0]["is_active"] == "True"


async def test_export_optional_fields_are_empty_string(client: AsyncClient, auth: dict):
    """Deposit without bank_name or close_date must export as empty string, not 'None'."""
    await client.post("/deposits", json={
        "title": "No optional",
        "amount": "1000",
        "currency": "RUB",
        "open_date": "2026-01-01",
        "annual_rate": "10.0",
    }, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=auth["headers"])
    rows = _csv_rows(_open_zip(resp.content)["deposits.csv"])
    assert rows[0]["bank_name"] == ""
    assert rows[0]["close_date"] == ""


async def test_export_multiple_deposits(client: AsyncClient, auth: dict):
    for i in range(3):
        await client.post("/deposits", json={**DEPOSIT, "title": f"Deposit {i}"}, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=auth["headers"])
    rows = _csv_rows(_open_zip(resp.content)["deposits.csv"])
    assert len(rows) == 3


async def test_export_scoped_to_user(client: AsyncClient, auth: dict, second_auth: dict):
    """User A's export must not contain User B's data."""
    await client.post("/deposits", json=DEPOSIT, headers=auth["headers"])
    resp = await client.get("/export/csv", headers=second_auth["headers"])
    rows = _csv_rows(_open_zip(resp.content)["deposits.csv"])
    assert len(rows) == 0


# ── Import: ZIP ───────────────────────────────────────────────────────────────

async def test_import_zip_creates_new_records(client: AsyncClient, auth: dict):
    # Export from one user
    await client.post("/deposits", json=DEPOSIT, headers=auth["headers"])
    await client.post("/subscriptions", json=SUBSCRIPTION, headers=auth["headers"])
    zip_bytes = (await client.get("/export/csv", headers=auth["headers"])).content

    # Import into a fresh second user
    resp = await client.post(
        "/import/csv",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        headers=auth["headers"],
    )
    # Everything already exists → all skipped
    assert resp.status_code == 200
    data = resp.json()
    assert data["deposits"] == 0
    assert data["subscriptions"] == 0
    assert data["skipped"] == 2


async def test_import_zip_deduplication(client: AsyncClient, auth: dict, second_auth: dict):
    """Importing another user's export should create new records (different ids don't clash)."""
    await client.post("/deposits", json=DEPOSIT, headers=auth["headers"])
    zip_bytes = (await client.get("/export/csv", headers=auth["headers"])).content

    # second_auth imports it → IDs don't exist for them → should create
    resp = await client.post(
        "/import/csv",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        headers=second_auth["headers"],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["deposits"] == 1
    assert data["skipped"] == 0

    # After import, second_auth can see the deposit
    deposits = (await client.get("/deposits", headers=second_auth["headers"])).json()
    assert len(deposits) == 1
    assert deposits[0]["title"] == "Export deposit"


async def test_import_zip_reimport_is_idempotent(client: AsyncClient, auth: dict, second_auth: dict):
    """Re-importing the same ZIP a second time must skip all rows."""
    await client.post("/deposits", json=DEPOSIT, headers=auth["headers"])
    zip_bytes = (await client.get("/export/csv", headers=auth["headers"])).content

    await client.post(
        "/import/csv",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        headers=second_auth["headers"],
    )
    resp2 = await client.post(
        "/import/csv",
        files={"file": ("export.zip", zip_bytes, "application/zip")},
        headers=second_auth["headers"],
    )
    assert resp2.json()["deposits"] == 0
    assert resp2.json()["skipped"] == 1


# ── Import: single CSV ────────────────────────────────────────────────────────

async def _make_deposits_csv(title: str = "Imported deposit") -> bytes:
    dep_id = str(uuid.uuid4())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "bank_name", "amount", "currency",
                "open_date", "close_date", "annual_rate", "created_at"])
    w.writerow([dep_id, title, "", "10000.00", "EUR",
                "2026-01-01", "", "8.0", "2026-01-01T00:00:00"])
    return buf.getvalue().encode()


async def _make_subscriptions_csv(title: str = "Imported sub") -> bytes:
    sub_id = str(uuid.uuid4())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "title", "category", "amount", "currency",
                "billing_cycle", "start_date", "end_date", "is_active", "created_at"])
    w.writerow([sub_id, title, "", "5.00", "EUR",
                "monthly", "2026-01-01", "", "True", "2026-01-01T00:00:00"])
    return buf.getvalue().encode()


async def test_import_single_deposits_csv(client: AsyncClient, auth: dict):
    csv_bytes = await _make_deposits_csv()
    resp = await client.post(
        "/import/csv",
        files={"file": ("deposits.csv", csv_bytes, "text/csv")},
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["deposits"] == 1
    deposits = (await client.get("/deposits", headers=auth["headers"])).json()
    assert any(d["title"] == "Imported deposit" for d in deposits)


async def test_import_single_subscriptions_csv(client: AsyncClient, auth: dict):
    csv_bytes = await _make_subscriptions_csv()
    resp = await client.post(
        "/import/csv",
        files={"file": ("subscriptions.csv", csv_bytes, "text/csv")},
        headers=auth["headers"],
    )
    assert resp.status_code == 200
    assert resp.json()["subscriptions"] == 1
    subs = (await client.get("/subscriptions", headers=auth["headers"])).json()
    assert any(s["title"] == "Imported sub" for s in subs)


async def test_import_single_csv_deduplication(client: AsyncClient, auth: dict):
    csv_bytes = await _make_deposits_csv("Once only")
    files = {"file": ("deposits.csv", csv_bytes, "text/csv")}
    await client.post("/import/csv", files=files, headers=auth["headers"])
    # Re-upload the same bytes (same id)
    resp = await client.post("/import/csv",
                             files={"file": ("deposits.csv", csv_bytes, "text/csv")},
                             headers=auth["headers"])
    assert resp.json()["deposits"] == 0
    assert resp.json()["skipped"] == 1


# ── Import: error cases ───────────────────────────────────────────────────────

async def test_import_unknown_csv_format_is_422(client: AsyncClient, auth: dict):
    csv_bytes = b"col1,col2\nval1,val2\n"
    resp = await client.post(
        "/import/csv",
        files={"file": ("unknown.csv", csv_bytes, "text/csv")},
        headers=auth["headers"],
    )
    assert resp.status_code == 422


async def test_import_response_schema(client: AsyncClient, auth: dict):
    csv_bytes = await _make_deposits_csv()
    resp = await client.post(
        "/import/csv",
        files={"file": ("deposits.csv", csv_bytes, "text/csv")},
        headers=auth["headers"],
    )
    data = resp.json()
    assert "deposits" in data
    assert "subscriptions" in data
    assert "skipped" in data
