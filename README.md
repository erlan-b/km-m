## Video

- https://www.youtube.com/watch?v=PUT_YOUR_VIDEO_ID_HERE

## Docker

### Windows

```powershell
cd C:\Users\User\Documents\GitHub\km-m\backend
docker compose up -d --build mysql backend admin
docker compose down
```

### Linux

```bash
cd /path/to/km-m/backend
docker compose up -d --build mysql backend admin
docker compose down
```

## Windows

### 1) MySQL

```powershell
cd C:\Users\User\Documents\GitHub\km-m\backend
docker compose up -d mysql
```

### 2) Backend

```powershell
cd C:\Users\User\Documents\GitHub\km-m\backend
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3) Admin

```powershell
cd C:\Users\User\Documents\GitHub\km-m\admin
pnpm install
pnpm dev
```

### 4) Mobile

```powershell
cd C:\Users\User\Documents\GitHub\km-m
powershell -NoProfile -ExecutionPolicy Bypass -File .\mobile\run_mobile.ps1 -Mode auto -SkipPubGet
```

## Linux

### 1) MySQL

```bash
cd /path/to/km-m/backend
docker compose up -d mysql
```

### 2) Backend

```bash
cd /path/to/km-m/backend
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### 3) Admin

```bash
cd /path/to/km-m/admin
pnpm install
pnpm dev
```

### 4) Mobile

```bash
cd /path/to/km-m
chmod +x ./mobile/run_mobile.sh
bash ./mobile/run_mobile.sh --mode auto --skip-pub-get
```

- email: admin@demo.kg
 - password: Admin12345! 
- Moderator:
 - email: moderator@demo.kg
 - password: Moderator12345! 
- User:
 - email: user@demo.kg
 - password: User12345!