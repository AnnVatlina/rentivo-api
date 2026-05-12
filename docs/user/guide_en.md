# Rentivo — User Guide

## What is Rentivo?

Rentivo is a personal finance tracker for managing:

- **Deposits** — track accrued interest, maturity dates, simple and compound rates.
- **Subscriptions** — recurring payments: streaming, software, gym, and everything else.
- **Properties** — purchase cost, utility expenses, rental income, and profit on sale.

The Analytics page shows income vs. expenses by month with a future forecast, plus a separate per-property expense chart.

Web app: **https://annvatlina.github.io/rentivo-ui/**  
API: **https://rentivo-api-production.up.railway.app**

---

## Getting Started

Open the app and register with your email and password. After logging in you land on the Dashboard with summary cards.

---

## Settings

The **Settings** page lets you:

- Set the **default currency** — used when creating deposits, subscriptions, and properties.
- Toggle **modules**: Deposits, Subscriptions, Property.
- Choose a **theme**: Indigo (purple), Neutral (greyscale), Dark.
- Load **demo data** or delete all account data.

> The Property module is off by default — enable it in Settings to see the tab in the sidebar.

---

## Deposits

### Deposits page

Table of all deposits: title, bank, amount, rate (with compound badge), close date, days elapsed, accrued income.

**Status indicators:**
- 🟢 Green dot — active
- 🟡 Amber row — expiring within 30 days (badge shows days remaining)
- Grey row — expired (Expired badge)

Click any column header to sort; click again to reverse direction. Pagination: 10 records per page.

The pencil button opens the edit form.

### Deposit form

**Simple interest:** fill in title, bank, amount, currency, open date, rate, close date, and select interest type = Simple.

**Compound interest:** select type = Compound, then choose compounding frequency: daily, monthly, quarterly, or annually.

Close date is optional — omit it for open-ended deposits.

---

## Subscriptions

### Subscriptions page

Filter tabs: **All** / **Active** / **One-time** / **Cancelled** — each shows a count.

Columns: title, category, cycle, amount, monthly equivalent, next payment.

**Next payment badges:**
- 🟡 Amber — payment due today or within 7 days (`today` / `Nd`)
- 🔵 Blue — payment due this calendar month (more than 7 days away)

The header shows a "N payment(s) this month" pill when applicable.

The `/ mo` total in the header counts **only monthly subscriptions** — yearly, quarterly, and biennial amounts are not prorated, consistent with how Analytics shows them as full amounts in the payment month.

### Subscription form

- **Billing cycle**: Weekly / Monthly / Quarterly / Yearly / **2 years** / One-time.
- A monthly cost preview appears below the amount field for non-monthly cycles.
- `end_date` is optional.

---

## Properties

### Properties list

**Click a row** → opens the property's **transaction view**.  
**Gear icon ⚙️** in the last column → opens the **edit form**.

### Property transactions (`/properties/:id`)

**Summary cards at the top:**
- **Total invested** — purchase price + all one-time expenses.
- **Expenses** — sum of all expense transactions, converted to the app's default currency.
- **Income received** — sum of all income transactions, converted to the app's default currency.
- **Profit / Status** — profit on sale, or Active badge.

> Conversion uses live exchange rates from open.er-api.com (24-hour cache). A loading indicator appears while rates are fetching.

**Filters:**
- Type: All / Expenses / Income.
- Category chips — only categories with data are shown, with counts.
- **Reset** button clears both filters.

**Table:**
- Columns: type icon, category, title, amount, `{default currency}` (converted), cycle, date.
- All columns are sortable — click the header.
- **Footer row** (`tfoot`) — totals for **all** filtered rows (not just the current page):
  - Amount column groups by actual transaction currency.
  - Base currency column shows the converted total.
- Pagination: 20 records per page, newest first by default.

**Adding a transaction** (Add button):
- Form expands above the table.
- Select type (Expense/Income), category from a dropdown, title, amount, currency, cycle, date.
- Categories: Utilities, Maintenance, Mortgage, Tax, Rent, Other.

### Property edit form (`/properties/:id/edit`)

Fields: name, address, purchase price, currency, purchase date, status.  
When status is **Sold**, additional fields appear: sale date, sale price, notes.  
The Delete button (with confirmation) removes the property and all its transactions.

### Importing transactions from a bank statement

If you have a bank CSV export, you can convert it for import:
1. Create the property in the app.
2. Copy its UUID from the address bar (`/properties/{uuid}`).
3. Prepare a CSV in `property_transactions.csv` format (see Export/Import) with `property_id` set to that UUID.
4. Upload via Import/Export.

---

## Analytics

### Main chart

Shows deposit income (green) and subscription expenses (red) bars by month.

- ← year → arrows switch the year.
- The currency dropdown selects the **display currency** — amounts are converted from native data currencies via open.er-api.com exchange rates.
- Transparent bars = projected (future months).
- Subscriptions with yearly / quarterly / biennial / weekly billing show the **full payment amount** in the payment month — not spread across months.

Summary cards below the chart: Income earned / Subs spent / Net (actual) / Net (full year incl. projected).

### Property chart

A second card below the main chart — property income and expenses by month.

- Property selector dropdown in the card header — switching instantly reloads data for that property.
- Shares the same year stepper and currency selector as the main chart.
- Automatically converts from the property's native currency if it differs from the selected one.
- Mini summary row below the chart: Expenses / Income / Net for actual months only.

---

## Export and Import

### Export

The **Export** button on the Import/Export page downloads a ZIP archive with four CSVs:
- `deposits.csv`
- `subscriptions.csv`
- `properties.csv`
- `property_transactions.csv`

Open in Excel or Google Sheets.

### Import

Drag and drop a file onto the upload zone, or click to browse. Accepts a ZIP (all four CSVs) or a single CSV file.

- Rows with an already-existing `id` are skipped — safe to re-import.
- Supports importing from another user's export (generates new UUIDs).
- For `property_transactions.csv` — the corresponding property must already exist in your account.

The result shows how many records were created and skipped per entity type.

---

## API Error Codes

| HTTP | Meaning |
|---|---|
| `401` | Token missing, expired, or invalid |
| `403` | Authorization header not sent, or module is disabled |
| `404` | Record does not exist or belongs to another user |
| `409` | Email already registered |
| `422` | Field validation error |
