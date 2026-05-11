# Rentivo — Руководство пользователя

## Что такое Rentivo?

Rentivo — личный финансовый трекер. Помогает следить за:

- **Вкладами** — сколько процентов накоплено, когда заканчивается срок.
- **Подписками** — регулярные платежи: стриминг, ПО, спортзал и всё остальное.
- **Недвижимостью** — покупка, аренда, расходы, прибыль при продаже.

Аналитика за год показывает по месяцам, сколько приносят вклады и недвижимость и сколько уходит на подписки и расходы.

---

## Начало работы

### Регистрация

```
POST /auth/register
{"email": "you@example.com", "password": "ваш-пароль"}
```

В ответ вы получите `access_token` и `refresh_token`.

### Вход

```
POST /auth/login
{"email": "you@example.com", "password": "ваш-пароль"}
```

### Как использовать токен

Каждый запрос (кроме регистрации и входа) должен содержать заголовок:

```
Authorization: Bearer <access_token>
```

### Обновление токена

Access-токен действует 30 минут. Чтобы получить новую пару без ввода пароля:

```
POST /auth/refresh
{"refresh_token": "<ваш-refresh-токен>"}
```

---

## Настройки

Настройки позволяют включать и выключать модули, а также задать валюту по умолчанию.

### Посмотреть настройки

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

### Изменить настройки

```
PUT /settings
```

Можно передать одно или несколько полей:

```json
{"module_property": true, "default_currency": "RUB"}
```

### Модули

| Модуль | Поле | По умолчанию |
|---|---|---|
| Вклады | `module_deposits` | включён |
| Подписки | `module_subscriptions` | включён |
| Недвижимость | `module_property` | выключен |

Отключённый модуль:
- Возвращает `403` при обращении к его эндпоинтам.
- Показывает `null` (а не `0`) в аналитике.

### Валюта по умолчанию

`default_currency` — ISO-код валюты: `USD`, `EUR`, `RUB`, `GEL`, `BYN`. Используется как дефолтное значение при создании вкладов, подписок, объектов недвижимости и в аналитике.

### Демо-данные

Чтобы быстро посмотреть, как работает приложение, загрузите демо-данные:

```
POST /settings/demo-data
```

Создаёт:
- 3 вклада (рублёвые простые/сложные + валютный)
- 6 подписок (Netflix, Spotify, Яндекс Плюс, iCloud, фитнес, Adobe CC)
- 1 объект недвижимости с транзакциями (аренда, управление, ремонт)

Все даты рассчитываются относительно сегодняшнего дня — данные всегда выглядят актуально.

Чтобы удалить все данные аккаунта:

```
DELETE /settings/data
```

Удаляет все вклады, подписки и объекты недвижимости. Настройки (модули, валюта) остаются.

---

## Вклады

### Добавить вклад

```
POST /deposits
```

**Простые проценты:**
```json
{
  "title": "Сбербанк 2026",
  "bank_name": "Сбербанк",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "close_date": "2026-12-31",
  "annual_rate": "17.0",
  "interest_type": "simple"
}
```

**Сложные проценты:**
```json
{
  "title": "Альфа-Банк",
  "amount": "100000.00",
  "currency": "RUB",
  "open_date": "2026-01-01",
  "annual_rate": "15.0",
  "interest_type": "compound",
  "compound_frequency": "monthly"
}
```

- `interest_type` — `simple` (простые) или `compound` (сложные). По умолчанию `simple`.
- `compound_frequency` — нужен только для сложных процентов: `daily`, `monthly`, `quarterly`, `annually`.
- `close_date` — необязательно; если не указана, вклад считается бессрочным.

### Посмотреть все вклады

```
GET /deposits
```

Каждый вклад содержит:
- `income_to_date` — накопленный доход на сегодня.
- `days_elapsed` — сколько дней вклад активен.

### Изменить / удалить

```
PUT /deposits/{id}   — частичное обновление
DELETE /deposits/{id}
```

---

## Подписки

### Добавить подписку

```
POST /subscriptions
{
  "title": "Netflix",
  "category": "Развлечения",
  "amount": "15.99",
  "currency": "USD",
  "billing_cycle": "monthly",
  "start_date": "2026-01-01"
}
```

- `billing_cycle`: `weekly`, `monthly`, `quarterly`, `yearly`, `one_time`.
- `end_date` — необязательно.
- `is_active` — по умолчанию `true`.

### Просмотр

```
GET /subscriptions
```

Каждая подписка содержит:
- `next_payment_date` — дата следующего списания.
- `monthly_cost` — стоимость, нормализованная к месяцу.

### Отменить / удалить

```
PUT /subscriptions/{id} {"is_active": false}
DELETE /subscriptions/{id}
```

---

## Недвижимость

Модуль нужно включить в настройках: `PUT /settings {"module_property": true}`.

### Добавить объект

```
POST /properties
{
  "name": "Квартира Москва",
  "address": "ул. Пушкина, 10",
  "purchase_date": "2020-01-01",
  "purchase_price": "5000000.00",
  "currency": "RUB",
  "status": "active"
}
```

При продаже укажите `status: "sold"`, `sale_date` и `sale_price`.

### Детали объекта

```
GET /properties/{id}
```

Возвращает объект + `summary`:
- `total_invested` — цена покупки + все разовые расходы.
- `profit` — прибыль (только для проданных объектов).

### Транзакции

Транзакции — доходы (аренда) и расходы (ремонт, коммуналка) по объекту.

```
POST /properties/{id}/transactions
```

**Разовый расход:**
```json
{
  "type": "expense",
  "category": "renovation",
  "title": "Ремонт кухни",
  "amount": "200000.00",
  "currency": "RUB",
  "billing_cycle": "one_time",
  "transaction_date": "2021-06-15"
}
```

**Регулярный доход (аренда):**
```json
{
  "type": "income",
  "category": "rent",
  "title": "Аренда",
  "amount": "50000.00",
  "currency": "RUB",
  "billing_cycle": "monthly",
  "start_date": "2022-01-01"
}
```

- Для `one_time` — указывайте `transaction_date`.
- Для повторяющихся — указывайте `start_date` (и опционально `end_date`).

### Аналитика по объекту

```
GET /properties/{id}/analytics?year=2026
```

Возвращает помесячный доход и расходы по объекту за год.

---

## Аналитика

```
GET /analytics?year=2026&currency=RUB
```

Возвращает 12 строк — по одной на каждый месяц:

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

- Прошедшие месяцы — фактические данные (`is_projected: false`).
- Будущие месяцы — прогноз (`is_projected: true`).
- Отключённые модули возвращают `null` в своих полях.
- Учитываются только записи в указанной валюте.

---

## Экспорт и импорт

### Экспорт

```
GET /export/csv
```

Скачивает ZIP-архив с четырьмя файлами:
- `deposits.csv`
- `subscriptions.csv`
- `properties.csv`
- `property_transactions.csv`

Файлы можно открыть в Excel или Google Таблицах.

### Импорт

```
POST /import/csv
Content-Type: multipart/form-data
file: <zip или csv>
```

- Принимает полный ZIP или один CSV.
- Строки с уже существующим `id` пропускаются — повторный импорт безопасен.
- Поддерживает импорт из чужого экспорта (генерирует новые UUID).

```json
// Ответ
{"deposits": 3, "subscriptions": 2, "properties": 1, "property_transactions": 5, "skipped": 0}
```

---

## Коды ошибок

| HTTP | Значение |
|---|---|
| `401` | Токен отсутствует, истёк или недействителен |
| `403` | Заголовок Authorization не передан, или модуль отключён |
| `404` | Запись не существует или принадлежит другому пользователю |
| `409` | Email уже зарегистрирован |
| `422` | Ошибка валидации поля |
