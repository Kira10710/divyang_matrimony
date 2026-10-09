# Project Roadmap: Divyang Matrimony

## Phase 1: Core Foundation & Authentication
- Setup database schema & Alembic migrations for Auth & Users.
- Implement FastAPI authentication endpoints (Mobile + OTP, JWT).
- Implement Flutter Clean Architecture setup, networking, and Auth UI.
- Secure session management and RBAC structure.

## Phase 2: Profile & Preferences
- Backend models, services, and APIs for Profile and Partner Preferences.
- Photo upload integration with Firebase Storage.
- Flutter UI for Profile creation, editing, and preferences.

## Phase 3: Discovery & Interactions
- Backend PostgreSQL queries for preference-based matching.
- APIs for browsing, filtering, and shortlisting profiles.
- Interest expression (send/accept/reject).
- Flutter UI for Discovery and Interest management.

## Phase 4: Privacy, Safety & Communications
- Implement Privacy Tiers and visibility rules on the server.
- WhatsApp handoff flow implementation.
- Consent and audit logging.
- Flutter UI for privacy controls and reporting.

## Phase 5: Notifications & Subscriptions
- FCM integration for push notifications.
- Razorpay integration for subscriptions.
- Flutter UI for plans and payment flow.

## Phase 6: Admin Panel
- Admin endpoints for user/verification management.
- Basic analytics and subscription monitoring.
- Flutter Web UI for Admin dashboard.
