# Divyang Matrimony

Matrimony platform for people with disabilities in India.

## Project Structure

```
Matrimony/
├── Architecture.md          # System architecture document (source of truth)
├── flutter_app/             # Flutter client (Android + Web)
└── backend/                 # FastAPI backend
```

## Tech Stack

| Layer | Technology |
|---|---|
| Mobile + Web Client | Flutter 3.x (Android + Web) |
| State Management | Riverpod 2.x |
| Routing | GoRouter |
| Backend | FastAPI + Python 3.12 |
| ORM | SQLAlchemy 2.x (async) |
| Database | PostgreSQL 16 |
| Migrations | Alembic |
| Cache | Redis 7.x (cache + rate-limit only) |
| Scheduled Jobs | APScheduler (in-process) |
| Object Storage | Firebase Storage |
| Push Notifications | Firebase Cloud Messaging |
| Payments | Razorpay (sandbox mode) |
| Containerization | Docker + Docker Compose |
| Error Tracking | Sentry |

## Getting Started

### Prerequisites

- Flutter SDK 3.x
- Python 3.12+
- Docker & Docker Compose
- Firebase project (dev)
- Razorpay sandbox account

### Backend Setup

```bash
cd backend

# 1. Copy environment template and fill in values
cp .env.example .env
# Edit .env with your database, Firebase, and Razorpay credentials

# 2. Start infrastructure with Docker
docker compose up -d db redis

# 3. Create virtual environment and install dependencies
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"

# 4. Run database migrations
python scripts/migrate.py

# 5. Create initial admin account
python scripts/create_admin.py

# 6. Start the API server
uvicorn app.main:app --reload --port 8000

# API docs available at http://localhost:8000/docs (dev only)
```

### Flutter Setup

```bash
cd flutter_app

# 1. Install dependencies
flutter pub get

# 2. Run code generation (models, providers)
dart run build_runner build --delete-conflicting-outputs

# 3. Run in dev mode
flutter run -t lib/main_dev.dart

# Or with explicit flavor
flutter run --dart-define=FLAVOR=dev
```

### Build Flavors

| Flavor | Entry Point | API Target | Notes |
|---|---|---|---|
| `dev` | `main_dev.dart` | `http://10.0.2.2:8000` | Local dev server, debug mode |
| `staging` | via `--dart-define=FLAVOR=staging` | `https://staging-api.divyangmatrimony.com` | Pre-production |
| `prod` | `main_prod.dart` | `https://api.divyangmatrimony.com` | Production release |

```bash
# Dev APK
flutter build apk -t lib/main_dev.dart --debug

# Production APK
flutter build apk -t lib/main_prod.dart --release

# Web (dev)
flutter build web -t lib/main_dev.dart
```

### Docker (Full Stack)

```bash
cd backend

# Start everything
docker compose up --build

# This starts:
#   - FastAPI on :8000
#   - PostgreSQL on :5432
#   - Redis on :6379
```

## Architecture

See [Architecture.md](Architecture.md) for the complete system design.

Key decisions documented there:
- **Riverpod** over BLoC (ADR-008)
- **No Celery** in v1 — APScheduler + BackgroundTasks (ADR-007)
- **WhatsApp deep-link** for chat v1 (ADR-004)
- **Live SQL matching** instead of precomputed suggestions (ADR-009)
- **`platform_id`** column for multi-platform reuse (Section 14)

## Testing

```bash
# Backend
cd backend
pytest                           # All tests
pytest tests/unit/               # Unit only
pytest --cov=app                 # With coverage

# Flutter
cd flutter_app
flutter test                     # Unit + widget tests
flutter test integration_test/   # Integration tests (requires device/emulator)
```

## License

Proprietary — all rights reserved.
