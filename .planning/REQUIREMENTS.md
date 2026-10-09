# Requirements: Divyang Matrimony

## MVP Features

### 1. Authentication
- Mobile number + OTP authentication.
- JWT authentication, session management, logout, session expiry handling.
- Admin authentication.

### 2. Profile Management
- Create, edit, and view profile.
- Profile completion tracking.
- Fields: Personal info, Education, Occupation, Location, Disability info, Managed-by (SELF/PARENT/SIBLING/GUARDIAN).
- Profile verification status.

### 3. Profile Photos
- Upload, delete, set primary photo (Firebase Storage).

### 4. Partner Preferences
- Age range, Location, Education, Occupation, Disability preferences, etc.

### 5. Discovery & Search
- Browse and filter profiles.
- Privacy rules applied to visibility.
- Basic preference-based matching (PostgreSQL queries, no AI for V1).

### 6. Interest & Shortlist
- Express interest, accept/reject interest, shortlist profiles.

### 7. Privacy & Safety
- Profile visibility controls & Privacy tiers (PUBLIC, REGISTERED, SUBSCRIBERS, MATCHED, PRIVATE).
- Sensitive info protection, reporting, verification, consent/audit logging.

### 8. Communication
- WhatsApp handoff/contact flow (no in-app chat for V1).

### 9. Notifications
- Push notifications for interests/matches/system via Firebase Cloud Messaging.

### 10. Subscriptions & Payments
- Subscription plans, Razorpay integration, payment tracking.

### 11. Admin
- Admin auth, user/profile/verification/report management, basic analytics, subscription monitoring.

## Non-Functional Requirements
- **Security**: JWT, server-side RBAC, AES-256-GCM encryption for sensitive data, revocable sessions.
- **Accessibility**: Readable typography, strong contrast, 48dp touch targets, screen-reader friendly, clear validation errors.
- **Multi-Platform**: Support configuration-driven platform scaling (e.g., `platform_id = divyang`).
- **Development**: Features must be built as vertical slices (Database -> Backend -> Flutter Model -> UI).
