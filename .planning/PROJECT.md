# Divyang Matrimony

## Core Purpose
Build a production-ready matrimonial platform called "Divyang Matrimony" for adults with disabilities seeking marriage/companionship. The platform must prioritize privacy, security, accessibility, trust and safety, clean UX, and a maintainable architecture. 

It is designed to be multi-platform (capable of supporting a future "Senior Citizen Matrimony" platform using the same backend/codebase via platform configuration).

## Target Audience
- **Primary**: Adults with disabilities looking for marriage/companionship. Profiles may be managed by SELF, PARENT, SIBLING, or GUARDIAN.
- **Future**: Senior citizens (via a separate platform).

## Tech Stack
- **Frontend**: Flutter (Android, Web, iOS later), Riverpod, Clean Architecture.
- **Backend**: Python, FastAPI, Pydantic, SQLAlchemy 2.x, Async PostgreSQL, Alembic, JWT.
- **Database**: PostgreSQL 16 (Docker for local dev).
- **Storage/Notifications**: Firebase Storage, Firebase Cloud Messaging.
- **Payments**: Razorpay.
- **Infrastructure**: Docker / Docker Compose, Ubuntu VPS, Nginx, HTTPS.
- **Future Options**: Redis, Celery, Meilisearch.

## Architecture Guidelines
- Clean Architecture, SOLID, Feature-first organization.
- Vertical slice development: DB -> Backend -> API -> Flutter Model -> UI -> Integration.
- See `Architecture.md` and `Database.md` in the root directory for authoritative source of truth.
