# Backend (FastAPI)

## Local setup

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
python -m app.db.seed
```

7. Start API:

```bash
uvicorn app.main:app --reload --port 8000
```

## First endpoints

- `GET /api/v1/health/live`
- `GET /api/v1/health/ready`
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/languages`
- `PATCH /api/v1/auth/me/language`
- `GET /api/v1/categories`
- `GET /api/v1/categories/admin`
- `POST /api/v1/categories`
- `PATCH /api/v1/categories/{category_id}`
- `POST /api/v1/categories/{category_id}/activate`
- `POST /api/v1/categories/{category_id}/deactivate`
- `POST /api/v1/listings`
- `GET /api/v1/listings/my`
- `PATCH /api/v1/listings/{listing_id}`
- `PATCH /api/v1/listings/{listing_id}/status`
- `PATCH /api/v1/listings/{listing_id}/moderation`
- `GET /api/v1/listings`
- `GET /api/v1/listings/{listing_id}`
- `POST /api/v1/favorites/{listing_id}`
- `DELETE /api/v1/favorites/{listing_id}`
- `GET /api/v1/favorites`
- `GET /api/v1/payments/me`
- `GET /api/v1/promotions/packages`
- `POST /api/v1/promotions/packages`
- `POST /api/v1/promotions/purchase`
- `GET /api/v1/promotions/me`
- `POST /api/v1/promotions/expire-premium`
- `POST /api/v1/reports`
- `GET /api/v1/reports/my`
- `GET /api/v1/reports/admin`
- `PATCH /api/v1/reports/{report_id}/resolve`
- `GET /api/v1/public/users/{user_id}`
- `GET /api/v1/public/users/{user_id}/listings`
