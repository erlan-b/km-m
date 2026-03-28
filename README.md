# KM-M — Real Estate Marketplace

Full-stack marketplace platform built with **FastAPI** (Python), **React** (Vite/TypeScript) admin panel, **MySQL** database, and designed for a **Flutter** mobile client.

**Domain:** Real estate — apartments, houses, commercial property, land, rooms.

---

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Flutter App  │────▶│   FastAPI     │────▶│    MySQL     │
│  (mobile)     │     │   Backend    │     │   Database   │
└──────────────┘     └──────┬───────┘     └──────────────┘
                           │
┌──────────────┐           │
│  React Admin │───────────┘
│  (Vite/TS)   │
└──────────────┘
```

- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2.x (async-compatible ORM), Alembic migrations, Pydantic v2 schemas, JWT auth (access + refresh tokens), bcrypt password hashing.
- **Admin Panel:** React 19, Vite 8, TypeScript, vanilla CSS. Fully localized (EN/RU).
- **Database:** MySQL 8.x, 21 Alembic migrations, relational schema with foreign keys, indexes, and constraints.
- **Mobile:** Flutter (planned). Backend API is fully prepared.

### Key Design Decisions

| Decision | Rationale |
|---|---|
| **JSON `dynamic_attributes`** on listings | Category-specific fields (rooms, area, floor for apartments; brand, model for cars) stored as validated JSON. Schema is defined per-category in `attributes_schema`. Chosen over separate typed tables for flexibility — new categories don't require migrations. |
| **Promotion/Payment separation** | `PromotionPackage` defines what can be purchased. `Payment` records the transaction. `Promotion` is activated only after successful payment confirmation — no boolean toggles. |
| **Subscription as listing-level flag** | `is_subscription` + `subscription_expires_at` on listings. Activated through payment flow, visible in admin dashboard. |
| **i18n: static + dynamic** | Base translations are static dictionaries in `i18n.py` (zero-latency). Dynamic overrides stored in `i18n_entries` table, manageable through admin panel without code deploys. |
| **Soft delete via status** | Listings use `ARCHIVED` / `INACTIVE` / `SOLD` statuses instead of hard delete. Users use `DEACTIVATED` status. |

---

## Database Schema

### Core Entities (15+ tables)

| Table | Purpose |
|---|---|
| `users` | Accounts with profile fields, status, preferred language |
| `roles` / `user_roles` | RBAC: guest, user, moderator, admin, support, superadmin |
| `categories` | Listing taxonomy with `attributes_schema` JSON, `display_order` |
| `listings` | Primary content. Price, location, coordinates, dynamic attributes, subscription flags |
| `listing_media` | Multiple images per listing, ordering, primary flag, thumbnails |
| `favorites` | User ↔ Listing M2M with unique constraint |
| `conversations` | Messaging threads linked to listings, two participants |
| `messages` | Text messages with read/unread state, soft-delete support |
| `message_attachments` | Files attached to messages (images, PDF) |
| `notifications` | 7 event types, read/unread tracking |
| `reports` / `report_attachments` | Abuse reporting with reasons, admin resolution workflow |
| `payments` | Transaction records: pending → successful/failed/cancelled/refunded |
| `promotion_packages` | Admin-defined packages with duration, price, targeting |
| `promotions` | User purchases: targeting city/category, status lifecycle |
| `admin_audit_logs` | All moderation actions recorded |
| `i18n_entries` | Dynamic translation overrides |
| `password_reset_tokens` | Forgot-password flow tokens |
| `refresh_tokens` | JWT refresh token storage with hash |

### Indexes

- `listings.status`, `listings.city`, `listings.category_id`, `listings.created_at`
- `payments.status`, `promotions.status`
- `conversations` participant IDs
- `favorites` unique `(user_id, listing_id)`
- `users.email` unique

---

## Setup Instructions

### Prerequisites

- Python 3.12+
- Node.js 18+ / pnpm
- MySQL 8.x (or Docker)
- Git

### 1. Clone & Configure

```bash
git clone <repository-url>
cd km-m
cp backend/.env.example backend/.env
# Edit backend/.env if needed (DB credentials, JWT secret)
```

### 2. Start MySQL

```bash
# Option A: Docker (recommended)
docker compose up -d mysql

# Option B: Local MySQL — create database manually
# CREATE DATABASE realestate_demo;
```

### 3. Backend

```bash
cd backend
python -m venv ../.venv          # or use existing venv
../.venv/Scripts/pip install -r requirements.txt

# Run migrations
../.venv/Scripts/python -m alembic upgrade head

# Seed demo data
../.venv/Scripts/python db/scripts/seed_basics.py --scope all
../.venv/Scripts/python db/scripts/seed_admin_panel_demo.py --users 30

# Start server
../.venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
```

Backend available at: `http://localhost:8000`
Swagger/OpenAPI: `http://localhost:8000/docs`

### 4. Admin Panel

```bash
cd admin
pnpm install
pnpm dev
```

Admin available at: `http://localhost:5173`

### 5. Docker Compose (Full Stack)

```bash
docker compose up -d --build mysql backend admin
```

---

## Environment Variables

All variables are in `backend/.env.example`. Key settings:

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET_KEY` | `change-me-for-local-dev` | **Must change in production** |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | `127.0.0.1` / `3306` / `realestate_demo` | MySQL connection |
| `DB_USER` / `DB_PASSWORD` | `root` / `root` | MySQL credentials |
| `SUPPORTED_LANGUAGES_CSV` | `en,ru` | Supported UI languages |
| `MEDIA_ROOT` | `storage` | Upload directory |
| `EXPOSE_PASSWORD_RESET_TOKEN` | `true` | Returns token in response (dev mode). Set `false` in production |
| `ENABLE_RATE_LIMIT` | `true` | Auth endpoint rate limiting |
| `CORS_ALLOWED_ORIGINS_CSV` | `localhost:3000,5173` | Allowed CORS origins |

---

## Demo Credentials

| Role | Email | Password |
|---|---|---|
| **Superadmin** | `superadmin@demo.kg` | `Superadmin12345!` |
| **Admin** | `admin@demo.kg` | `Admin12345!` |
| **Moderator** | `moderator@demo.kg` | `Moderator12345!` |
| **Support** | `support@demo.kg` | `Support12345!` |
| **User** | `user@demo.kg` | `User12345!` |

Run `seed_basics.py --scope all` to create these accounts.

---

## API Route Summary

| Group | Endpoints | Auth |
|---|---|---|
| `/auth` | register, login, logout, refresh, forgot-password, reset-password, change-password, me | Public / Authenticated |
| `/profile` | GET, PATCH, POST avatar | Authenticated |
| `/public/users` | GET user, GET user listings | Public |
| `/categories` | CRUD + admin management | Public read / Admin write |
| `/listings` | CRUD, search, filter, sort, pagination, status transitions, admin moderation | Mixed |
| `/listing-media` | Upload, reorder, set primary, delete | Owner / Admin |
| `/favorites` | Add, remove, list | Authenticated |
| `/conversations` | List, create, detail | Authenticated |
| `/messages` | Send, list in conversation | Authenticated (participant) |
| `/attachments` | Upload to message, download | Authenticated (participant) |
| `/notifications` | List, mark read, unread count | Authenticated |
| `/reports` | Create, list own, admin management | Authenticated / Admin |
| `/payments` | Create, confirm, user history, admin list | Authenticated / Admin |
| `/promotions` | Purchase, user list, admin CRUD packages, admin list | Authenticated / Admin |
| `/i18n` | Page translations, admin entry CRUD | Public read / Admin write |
| `/admin/dashboard` | Aggregated statistics | Admin |
| `/admin/users` | Search, detail, suspend/unsuspend, inspect related | Admin |
| `/admin/messages` | Conversation oversight | Admin |
| `/admin/audit-logs` | Browse audit trail | Admin |

---

## Payment & Promotion Flow

Payments use a **mock gateway** architecture designed for easy replacement with a real provider.

```
1. User selects promotion package      POST /promotions/purchase
2. Payment record created              → Payment(status=pending)
3. User "pays" (mock confirmation)     POST /payments/{id}/confirm
4. On success:
   - Payment.status → successful
   - Promotion.status → active
   - Promotion.starts_at / ends_at set
   - If subscription: listing.is_subscription → true
5. On failure:
   - Payment.status → failed
   - No promotion activation
```

The system distinguishes payment intent → provider confirmation → business activation. No boolean toggles without transaction records.

**Promotion targeting:** city-based, category-based, or both. Duration from package definition. Price stored on both package (catalog) and promotion (purchased price at time of purchase).

---

## Localization

- **Supported languages:** English (en), Russian (ru)
- **User preference:** stored in `users.preferred_language`
- **Backend:** returns machine-readable enum codes for statuses. Translation dictionaries in `i18n.py` (1200+ entries covering all admin pages)
- **Admin panel:** fully localized. Language toggle in topbar switches all UI text
- **Content translations:** admin can manage category names and promotion package titles in both languages through the Localization page
- **Dynamic overrides:** `i18n_entries` table allows DB-level text overrides without code deploy

---

## Testing

16 test files in `backend/tests/`:

| Test File | Coverage |
|---|---|
| `test_auth_lifecycle.py` | Registration, login, token refresh, password flows |
| `test_role_matrix_access.py` | RBAC permission checks across all roles |
| `test_listing_soft_delete.py` | Listing status transitions, archive/restore |
| `test_listing_recommended_features.py` | Search, filters, sorting, dynamic attributes |
| `test_messaging_access_control.py` | Conversation participant checks |
| `test_promotions_payments_flow.py` | Purchase → payment → activation lifecycle |
| `test_payments_admin.py` | Admin payment management |
| `test_reports_workflow.py` | Report creation → admin resolution |
| `test_user_profile_fields.py` | Profile CRUD, avatar upload |
| `test_admin_audit_logs.py` | Audit trail recording |
| `test_admin_linked_entities_flow.py` | Cross-entity admin inspections |
| `test_category_display_order.py` | Category ordering logic |
| `test_i18n_*.py` (3 files) | Translation CRUD, page delivery, auth messages |

Run tests:
```bash
cd backend
../.venv/Scripts/python -m pytest tests/ -v
```

---

## Admin Panel Features

| Section | Capabilities |
|---|---|
| **Dashboard** | KPIs (users, listings, reports, promotions), detailed stats grid, quick actions |
| **Users** | Search, detail view, suspend/unsuspend, inspect related listings/payments/reports |
| **Listings Moderation** | Filter by status/category/city/owner, approve, reject with note, archive |
| **Reports** | Browse queue, filter by status/reason, resolve/dismiss, inspect target |
| **Categories** | Create, edit, enable/disable, reorder, manage attribute schemas |
| **Payments** | View records, filter by status/provider/date, inspect linked entities |
| **Promotions** | View active/expired, create/edit packages, deactivate |
| **Messages** | Conversation oversight for abuse investigation |
| **Audit Logs** | Browse all moderation actions with timestamps and actors |
| **Localization** | Manage category and promotion package translations (EN/RU) |

---

## Known Limitations

1. **Payment gateway is mocked.** `POST /payments/{id}/confirm` simulates provider callback. Architecture supports real provider integration (payment intent → callback → activation).
2. **No real-time messaging.** Messages are fetched via REST polling. WebSocket layer can be added.
3. **No email delivery.** Password reset tokens are returned in API response (`EXPOSE_PASSWORD_RESET_TOKEN=true`). Production would integrate SMTP/SendGrid.
4. **No push notifications.** Notifications are DB-backed only. FCM integration planned for mobile.
5. **File storage is local.** `MEDIA_ROOT=storage` directory. Production would use GCS/S3 with signed URLs.

## Future Work

- Flutter mobile application (backend API fully prepared)
- WebSocket real-time messaging
- GCP Cloud Storage for media
- FCM push notifications
- Email verification flow
- Real payment provider integration (Stripe/PayBox)
- Advanced analytics dashboards (charts, trends)
- Wallet/balance system
