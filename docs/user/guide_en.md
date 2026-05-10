# Rentivo API — User Guide

## What is Rentivo?

Rentivo is a personal finance API that helps you track two things:

- **Bank deposits** — how much interest you are earning and when a deposit closes.
- **Subscriptions** — recurring payments like streaming services, software, or gym memberships.

The API provides a monthly analytics view so you can see at a glance how much income your deposits are generating versus how much your subscriptions are costing you.

---

## Getting Started

### Register

Create an account by sending your email and password:

```
POST /auth/register
{
  "email": "you@example.com",
  "password": "your-password"
}
```

You receive an `access_token` and a `refresh_token`. Store both.

### Log In

If you already have an account:

```
POST /auth/login
{
  "email": "you@example.com",
  "password": "your-password"
}
```

### Use the Access Token

Every request to deposits, subscriptions, or analytics must include:

```
Authorization: Bearer <access_token>
```

### Refresh Your Token

Access tokens expire after 30 minutes. Use the refresh token to get a new pair without re-entering your password:

```
POST /auth/refresh
{
  "refresh_token": "<your-refresh-token>"
}
```

---

## Deposits

### Add a Deposit

```
POST /deposits
{
  "title": "Sberbank savings 2026",
  "bank_name": "Sberbank",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "close_date": "2026-12-31",
  "annual_rate": "17.0"
}
```

- `currency` must be one of: `USD`, `EUR`, `RUB`, `GEL`, `BYN`.
- `close_date` is optional — leave it out for open-ended deposits.
- `annual_rate` is the annual percentage, e.g. `17.0` means 17%.

### View All Deposits

```
GET /deposits
```

Each deposit in the list includes two calculated fields:

- `income_to_date` — interest earned so far using simple interest formula.
- `days_elapsed` — how many days the deposit has been active (capped at the close date if it has passed).

### View a Single Deposit

```
GET /deposits/{id}
```

### Edit a Deposit

```
PUT /deposits/{id}
{
  "title": "Renamed deposit"
}
```

All fields are optional — only send what you want to change.

### Delete a Deposit

```
DELETE /deposits/{id}
```

---

## Subscriptions

### Add a Subscription

```
POST /subscriptions
{
  "title": "Netflix",
  "category": "Entertainment",
  "amount": "15.99",
  "currency": "USD",
  "billing_cycle": "monthly",
  "start_date": "2026-01-01"
}
```

- `billing_cycle` options: `weekly`, `monthly`, `quarterly`, `yearly`, `one_time`.
- `end_date` is optional — use it when you know when the subscription will end.
- `is_active` defaults to `true`.

### View Subscriptions

```
GET /subscriptions
```

You can filter the list:

```
GET /subscriptions?filter=active      — only active recurring subscriptions
GET /subscriptions?filter=cancelled   — only cancelled subscriptions
GET /subscriptions?filter=one_time    — only one-time payments
```

Each subscription shows:

- `next_payment_date` — when the next charge is expected (calculated automatically).
- `monthly_cost` — the subscription cost normalized to a monthly amount.

### Cancel a Subscription

```
PUT /subscriptions/{id}
{
  "is_active": false
}
```

### Delete a Subscription

```
DELETE /subscriptions/{id}
```

---

## Analytics

Get a full year breakdown of your income versus spending:

```
GET /analytics?year=2026&currency=RUB
```

The response contains a row for each of the 12 months:

```json
{
  "year": 2026,
  "currency": "RUB",
  "months": [
    {
      "month": 1,
      "year": 2026,
      "deposit_income": "2301.37",
      "subscription_expenses": "1200.00",
      "net": "1101.37",
      "is_projected": false
    },
    ...
  ]
}
```

- Months in the past show **actual** figures (`is_projected: false`).
- Months from today onward show **projected** figures (`is_projected: true`), based on your current deposits and active subscriptions.
- Only deposits and subscriptions in the requested `currency` are included.

---

## Exporting Your Data

Download all your deposits and subscriptions as a ZIP file containing two CSV files:

```
GET /export/csv
```

Save the ZIP — it contains `deposits.csv` and `subscriptions.csv`. You can open them in Excel, Google Sheets, or any spreadsheet app.

---

## Importing Data

If you have data from another source or a previous export, you can import it:

```
POST /import/csv
Content-Type: multipart/form-data
file: <your-zip-or-csv-file>
```

- You can upload either the full ZIP or a single CSV file.
- Rows whose `id` already exists in your account are **skipped** (safe to re-import).
- The response tells you how many records were created and how many were skipped.

---

## Error Reference

| HTTP status | Meaning |
|---|---|
| `400 Bad Request` | The request body is malformed or a required field is missing |
| `401 Unauthorized` | Token is missing, expired, or invalid |
| `403 Forbidden` | No `Authorization` header was provided |
| `404 Not Found` | The record does not exist or belongs to a different user |
| `409 Conflict` | Email is already registered |
| `422 Unprocessable Entity` | Field validation failed (e.g. negative amount, unrecognized currency) |
