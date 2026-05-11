# Rentivo — User Guide

## What is Rentivo?

Rentivo is a personal finance tracker. It helps you manage:

- **Deposits** — how much interest you are earning and when a deposit closes.
- **Subscriptions** — recurring payments: streaming, software, gym, etc.
- **Properties** — purchases, rental income, expenses, and profit on sale.

The monthly analytics view shows income vs. expenses by month, with a forecast for future months.

---

## Getting Started

### Register

```
POST /auth/register
{"email": "you@example.com", "password": "your-password"}
```

Returns `access_token` and `refresh_token`.

### Login

```
POST /auth/login
{"email": "you@example.com", "password": "your-password"}
```

### Using the token

Every request (except register and login) requires:

```
Authorization: Bearer <access_token>
```

### Refreshing tokens

Access tokens expire in 30 minutes. To get a new pair without re-entering your password:

```
POST /auth/refresh
{"refresh_token": "<your-refresh-token>"}
```

---

## Settings

Settings let you toggle modules on/off and set a default currency.

### Get settings

```
GET /settings
```

```json
{
  "module_deposits": true,
  "module_subscriptions": true,
  "module_property": false,
  "default_currency": "USD"
}
```

### Update settings

```
PUT /settings
```

Pass any subset of fields:

```json
{"module_property": true, "default_currency": "EUR"}
```

### Modules

| Module | Field | Default |
|---|---|---|
| Deposits | `module_deposits` | enabled |
| Subscriptions | `module_subscriptions` | enabled |
| Property | `module_property` | disabled |

A disabled module:
- Returns `403` on its endpoints.
- Returns `null` (not `0`) in analytics.

### Default currency

`default_currency` — ISO currency code: `USD`, `EUR`, `RUB`, `GEL`, `BYN`. Used as the pre-selected value when creating deposits, subscriptions, properties, and in analytics.

---

## Deposits

### Add a deposit

```
POST /deposits
```

**Simple interest:**
```json
{
  "title": "Sberbank 2026",
  "bank_name": "Sberbank",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "close_date": "2026-12-31",
  "annual_rate": "17.0",
  "interest_type": "simple"
}
```

**Compound interest:**
```json
{
  "title": "Alpha Bank",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "annual_rate": "15.0",
  "interest_type": "compound",
  "compound_frequency": "monthly"
}
```

- `interest_type` — `simple` or `compound`. Default: `simple`.
- `compound_frequency` — required for compound: `daily`, `monthly`, `quarterly`, `annually`.
- `close_date` — optional; omit for open-ended deposits.

### List deposits

```
GET /deposits
```

Each deposit includes:
- `income_to_date` — accrued interest as of today.
- `days_elapsed` — number of active days.

### Update / delete

```
PUT /deposits/{id}   — partial update
DELETE /deposits/{id}
```

---

## Subscriptions

### Add a subscription

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

- `billing_cycle`: `weekly`, `monthly`, `quarterly`, `yearly`, `one_time`.
- `end_date` — optional.
- `is_active` — default `true`.

### List subscriptions

```
GET /subscriptions
```

Each subscription includes:
- `next_payment_date` — calculated automatically.
- `monthly_cost` — amount normalized to a monthly equivalent.

### Cancel / delete

```
PUT /subscriptions/{id} {"is_active": false}
DELETE /subscriptions/{id}
```

---

## Properties

Enable the module first: `PUT /settings {"module_property": true}`.

### Add a property

```
POST /properties
{
  "name": "Flat Moscow",
  "address": "Pushkin St, 10",
  "purchase_date": "2020-01-01",
  "purchase_price": "5000000.00",
  "currency": "RUB",
  "status": "active"
}
```

When sold, include `status: "sold"`, `sale_date`, and `sale_price`.

### Property detail

```
GET /properties/{id}
```

Returns the property plus `summary`:
- `total_invested` — purchase price + all one-time expenses.
- `profit` — profit on sale (only for sold properties).

### Transactions

Transactions track income (rent) and expenses (repairs, utilities) for a property.

```
POST /properties/{id}/transactions
```

**One-time expense:**
```json
{
  "type": "expense",
  "category": "renovation",
  "title": "Kitchen repair",
  "amount": "200000.00",
  "currency": "RUB",
  "billing_cycle": "one_time",
  "transaction_date": "2021-06-15"
}
```

**Recurring income (rent):**
```json
{
  "type": "income",
  "category": "rent",
  "title": "Monthly rent",
  "amount": "50000.00",
  "currency": "RUB",
  "billing_cycle": "monthly",
  "start_date": "2022-01-01"
}
```

- For `one_time` — use `transaction_date`.
- For recurring — use `start_date` (and optionally `end_date`).

### Property analytics

```
GET /properties/{id}/analytics?year=2026
```

Returns monthly income and expenses for the property.

---

## Analytics

```
GET /analytics?year=2026&currency=RUB
```

Returns 12 rows — one per month:

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
      "property_income": "50000.00",
      "property_expenses": "0.00",
      "net": "51101.37",
      "is_projected": false
    }
  ]
}
```

- Past months — actual data (`is_projected: false`).
- Future months — forecast (`is_projected: true`).
- Disabled module fields return `null`.
- Only records in the specified currency are included.

---

## Export and Import

### Export

```
GET /export/csv
```

Downloads a ZIP archive with four files:
- `deposits.csv`
- `subscriptions.csv`
- `properties.csv`
- `property_transactions.csv`

Open in Excel or Google Sheets.

### Import

```
POST /import/csv
Content-Type: multipart/form-data
file: <zip or csv>
```

- Accepts the full ZIP or a single CSV.
- Rows with an already-existing `id` are skipped — safe to re-import.
- Supports importing from another user's export (generates new UUIDs).

```json
// Response
{"deposits": 3, "subscriptions": 2, "properties": 1, "property_transactions": 5, "skipped": 0}
```

---

## Error Codes

| HTTP | Meaning |
|---|---|
| `401` | Token missing, expired, or invalid |
| `403` | Authorization header not sent, or module is disabled |
| `404` | Record does not exist or belongs to another user |
| `409` | Email already registered |
| `422` | Field validation error |
