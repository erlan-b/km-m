# Backend (FastAPI)

## Project Overview

This backend is a production-style API for a real-estate marketplace in Kyrgyzstan.
It implements end-to-end marketplace flows for:

- authentication and account lifecycle
- listings, media, search, filtering, and owner pages
- favorites, messaging, attachments, and notifications
- reports/moderation/audit logs
- payments and subscription promotions
- localization content management
- admin operational APIs

## Chosen Domain

Real-estate marketplace (sale, long-term rent, daily rent), aligned with the project scope and OSM location requirements.

## Architecture

- API framework: FastAPI
- Data layer: SQLAlchemy ORM + Alembic migrations
- Database: MySQL
- Auth: JWT access/refresh strategy with server-side refresh token storage
- Validation: Pydantic schemas
- Storage: local media root (`MEDIA_ROOT`) for listing media and message attachments
- Production hardening: global exception handlers, unified error envelope, CORS/TrustedHost/GZip middleware, basic rate limiting for auth and sensitive write routes

Code structure:

- `app/api/v1/endpoints`: route groups by domain
- `app/models`: ORM entities
- `app/schemas`: request/response contracts
- `app/services`: business helpers
- `app/core`: config/security
- `app/db`: session, base, seeds

## Database Notes

Core entities include: users/roles, categories, listings, listing_media, favorites, conversations, messages,
message_attachments, notifications, reports, payments, promotions, promotion_packages, admin_audit_logs,
localization_entries.

Key design points:

- listing statuses and moderation transitions are enforced server-side
- unique favorite constraint per user/listing
- role-based and ownership checks on protected operations
- soft-delete/archival strategy for listings with optional hard-delete for archived records
- subscription activation is tied to successful payment records

## Local Setup

1. Create and activate virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy env file:

```bash
cp .env.example .env
```

4. Start MySQL from project root:

```bash
docker compose up -d mysql
```

5. Run migrations:

```bash
alembic upgrade head
```

6. Seed categories:

```bash
python db/scripts/seed_basics.py --scope categories
```

7. Seed demo accounts (user/admin/moderator):

```bash
python db/scripts/seed_basics.py --scope users
```

8. Start API:

```bash
uvicorn app.main:app --reload --port 8000
```

## Backend Run Steps

1. Apply migrations.
2. Seed categories and demo users.
3. Start Uvicorn.
4. Open Swagger at `http://127.0.0.1:8000/docs`.

## Admin Run Steps

This repository currently provides admin functionality via protected backend endpoints (Swagger/API-first admin operations).

1. Login with admin credentials (see Demo Credentials).
2. Use `/api/v1/admin/...` and moderation endpoints from Swagger.
3. Review audit traces via `/api/v1/admin/audit-logs`.

## Mobile Run Steps

Flutter app is expected to consume this API via `API_V1_PREFIX` routes.
If mobile code is in a separate repository/folder, configure its base URL to this backend and run the required flows from the spec.

## Environment Variables

Core variables (see `.env.example` for full list):

- `APP_NAME`, `APP_ENV`, `DEBUG`, `API_V1_PREFIX`
- `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- `REFRESH_TOKEN_EXPIRE_DAYS`, `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES`
- `SUPPORTED_LANGUAGES_CSV`, `EXPOSE_PASSWORD_RESET_TOKEN`
- `MEDIA_ROOT` and media upload constraints/mime lists
- `CORS_ALLOWED_ORIGINS_CSV`, `CORS_ALLOWED_METHODS_CSV`, `CORS_ALLOWED_HEADERS_CSV`, `CORS_ALLOW_CREDENTIALS`
- `TRUSTED_HOSTS_CSV`, `GZIP_MINIMUM_SIZE`
- `ENABLE_RATE_LIMIT`, `AUTH_RATE_LIMIT_*`, `SENSITIVE_RATE_LIMIT_*`
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

Do not commit real secrets.

## First endpoints

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `POST /api/v1/auth/forgot-password`
- `POST /api/v1/auth/reset-password`
- `POST /api/v1/auth/change-password`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/languages`
- `PATCH /api/v1/auth/me/language`
- `GET /api/v1/localization/content`
- `GET /api/v1/localization/admin/entries`
- `POST /api/v1/localization/admin/entries`
- `PATCH /api/v1/localization/admin/entries/{entry_id}`
- `POST /api/v1/localization/admin/entries/{entry_id}/activate`
- `POST /api/v1/localization/admin/entries/{entry_id}/deactivate`
- `GET /api/v1/admin/dashboard`
- `GET /api/v1/admin/audit-logs`
- `GET /api/v1/admin/users`
- `GET /api/v1/admin/users/{user_id}`
- `POST /api/v1/admin/users/{user_id}/suspend`
- `POST /api/v1/admin/users/{user_id}/unsuspend`
- `GET /api/v1/admin/messages/conversations`
- `GET /api/v1/admin/messages/conversations/{conversation_id}`
- `GET /api/v1/admin/messages?conversation_id=...`
- `GET /api/v1/admin/messages/attachments/{attachment_id}/download`
- `GET /api/v1/categories`
- `GET /api/v1/categories/admin`
- `POST /api/v1/categories` (supports `attributes_schema` for category-specific dynamic fields)
- `PATCH /api/v1/categories/{category_id}` (supports `attributes_schema` updates)
- `POST /api/v1/categories/{category_id}/activate`
- `POST /api/v1/categories/{category_id}/deactivate`
- `POST /api/v1/listings` (supports `dynamic_attributes` validated against category schema)
- `GET /api/v1/listings/my`
- `PATCH /api/v1/listings/{listing_id}` (supports `dynamic_attributes` validated against category schema)
- `DELETE /api/v1/listings/{listing_id}` (soft-delete: archives listing)
- `POST /api/v1/listings/{listing_id}/restore` (restore archived listing to moderation queue)
- `DELETE /api/v1/listings/{listing_id}/hard` (permanent delete, only for archived listings)
- `GET /api/v1/listings/admin/moderation` (admin/moderator listing queue with filters)
- `PATCH /api/v1/listings/{listing_id}/status`
- `PATCH /api/v1/listings/{listing_id}/moderation`
- `GET /api/v1/listings` (supports `q` for title/description keyword search and `min_price`/`max_price` range filters)
- `GET /api/v1/listings/{listing_id}`
- `GET /api/v1/listing-media/listings/{listing_id}`
- `GET /api/v1/listing-media/listings/{listing_id}/my`
- `POST /api/v1/listing-media/listings/{listing_id}/upload`
- `POST /api/v1/listing-media/{media_id}/set-primary`
- `PATCH /api/v1/listing-media/{media_id}/order`
- `PUT /api/v1/listing-media/{media_id}/replace`
- `DELETE /api/v1/listing-media/{media_id}`
- `GET /api/v1/listing-media/{media_id}/download`
- `GET /api/v1/listing-media/{media_id}/download/my`
- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{notification_id}/read`
- `POST /api/v1/conversations`
- `GET /api/v1/conversations`
- `GET /api/v1/conversations/{conversation_id}`
- `GET /api/v1/messages`
- `POST /api/v1/messages/text`
- `POST /api/v1/messages`
- `POST /api/v1/messages/{message_id}/read`
- `GET /api/v1/attachments/{attachment_id}`
- `GET /api/v1/attachments/{attachment_id}/download`
- `POST /api/v1/favorites/{listing_id}`
- `DELETE /api/v1/favorites/{listing_id}`
- `GET /api/v1/favorites`
- `GET /api/v1/payments/me`
- `GET /api/v1/payments/admin` (filters: status, provider, user, listing, package, created/paid date range)
- `GET /api/v1/promotions/packages`
- `POST /api/v1/promotions/packages`
- `POST /api/v1/promotions/purchase`
- `GET /api/v1/promotions/me`
- `GET /api/v1/promotions/admin` (filters: status, user, listing, package, target city/category, starts/ends date range)
- `POST /api/v1/promotions/expire-subscription`
- `POST /api/v1/reports`
- `GET /api/v1/reports/my`
- `GET /api/v1/reports/admin`
- `PATCH /api/v1/reports/{report_id}/resolve`
- `GET /api/v1/public/users/{user_id}`
- `GET /api/v1/public/users/{user_id}/listings`

## Testing

Run all backend tests:

```bash
pytest tests -q
```

Current integration suites cover:

- auth lifecycle (`tests/test_auth_lifecycle.py`)
- listings lifecycle and delete policy (`tests/test_listing_soft_delete.py`)
- i18n public/auth/admin coverage (`tests/test_i18n_pages.py`, `tests/test_i18n_auth_messages.py`, `tests/test_i18n_admin_crud.py`)
- messaging/attachments access control (`tests/test_messaging_access_control.py`)
- payments/promotions activation rules (`tests/test_promotions_payments_flow.py`, `tests/test_payments_admin.py`)
- reports moderation workflow (`tests/test_reports_workflow.py`)
- role matrix access policy (`tests/test_role_matrix_access.py`)

## Demo Credentials

After running `python db/scripts/seed_basics.py --scope users`:

- Superadmin:
	- email: `superadmin@demo.kg`
	- password: `Superadmin12345!`
- Admin:
	- email: `admin@demo.kg`
	- password: `Admin12345!`
- Support:
	- email: `support@demo.kg`
	- password: `Support12345!`
- Moderator:
	- email: `moderator@demo.kg`
	- password: `Moderator12345!`
- User:
	- email: `user@demo.kg`
	- password: `User12345!`

## Payment and Promotion Assumptions

- provider integration is mocked via `payment_provider` and `simulate_success`
- every promotion purchase creates a payment record first
- promotion and subscription flags activate only when payment becomes `successful`
- failed payment does not create active promotion state
- subscription duration is package-driven (`duration_days`)

## Localization Support

- user preferred language is stored in profile
- supported languages are exposed via `/api/v1/auth/languages`
- backend page dictionaries are exposed via `/api/v1/i18n/pages` and `/api/v1/i18n/pages/{page_key}`
- admin localization CRUD is available via `/api/v1/i18n/admin/entries`
- public i18n page responses merge static dictionaries with active DB overrides

## Known Limitations

- payment provider callbacks are simulated, not integrated with a live provider
- README demo video link must be filled before final submission

## Future Work

- add dedicated admin frontend panel over existing admin APIs
- integrate real payment gateway callback flow with idempotency handling
- add richer analytics endpoints/charts and operational trend metrics
- expand localized content to category/package display labels in multiple languages
- extend automated test coverage with contract/e2e tests

## Demo Video

Add final demo video link here before submission:

- `TODO: insert demo video URL`
