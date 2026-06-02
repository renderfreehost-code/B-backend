# Backend

FastAPI backend for Render Web Service.

## Render settings

```text
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Required env

```env
DATABASE_URL=postgresql://...
JWT_SECRET=long_random_secret
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=StrongPassword123
CORS_ORIGINS=https://frontend-url
```
