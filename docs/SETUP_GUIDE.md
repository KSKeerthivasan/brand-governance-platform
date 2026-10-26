# Inkloom AI — Setup & Deployment Guide

## Prerequisites
- **Python**: 3.10+ (Tested on Python 3.12.10)
- **Node.js**: 18+ (Tested on Node v22.23.2 & npm 10.9.8)
- **Database**: PostgreSQL 18 or built-in SQLite fallback (zero-configuration)

---

## 1. Backend Setup

```powershell
cd e:\CodeStar30\backend

# 1. Install dependencies
pip install -r requirements.txt

# 2. Configure environment
# Copy .env.example to .env (already configured for local zero-friction setup)
cp .env.example .env

# 3. Run Alembic Database Migrations
python -m alembic upgrade head

# 4. Seed Synthetic Freshsip Demo Data
python seed.py

# 5. Run Backend Tests
python -m pytest tests -v

# 6. Start FastAPI Development Server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Backend will be accessible at:
- API Base: `http://127.0.0.1:8000/api/v1`
- Interactive Swagger Docs: `http://127.0.0.1:8000/docs`
- Health Endpoint: `http://127.0.0.1:8000/health`

---

## 2. Frontend Setup

```powershell
cd e:\CodeStar30\frontend

# 1. Install dependencies
npm install

# 2. Run Automated Component Tests
npm run test

# 3. Build for Production Verification
npm run build

# 4. Start Vite Development Server
npm run dev
```

Frontend will be accessible at:
- Web Application: `http://localhost:5173/`

---

## 3. Database & Managed Services Configuration

### Local PostgreSQL Connection (Default)
By default, `backend/.env` points to:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inkloom_ai
SQLITE_FALLBACK_URL=sqlite:///./inkloom_ai.db
```
If your local PostgreSQL server is running with custom credentials, update `DATABASE_URL` in `backend/.env`. If PostgreSQL is unreachable, the system automatically and smoothly falls back to SQLite (`./inkloom_ai.db`) so development and tests are never blocked.

### Supabase Cloud Deployment Configuration (Optional)
To use Supabase for managed Auth and private object storage:
1. Create a Supabase project at [supabase.com](https://supabase.com).
2. Set the environment variables in `backend/.env`:
```env
STORAGE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-publishable-key
SUPABASE_SERVICE_KEY=your-private-service-role-key
SUPABASE_STORAGE_BUCKET=inkloom-private-assets
```
3. Use the hosted PostgreSQL connection string in `DATABASE_URL`.
