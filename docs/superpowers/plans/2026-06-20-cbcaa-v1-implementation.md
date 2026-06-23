# CBCAA v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build CBCAA v1 as a standalone hosted account authority for A.S.S. beta with secure signup, MFA, command-code enforcement, direct entitlements, Stripe activation, device binding, launch tickets, and minimal admin recovery tooling.

**Architecture:** CBCAA ships as a standalone FastAPI monolith in `I:\Bosscrafts\CBCAA` with modular backend packages for identity, auth, command codes, devices, entitlements, billing, tickets, admin, and audit. The first implementation should favor a production-shaped backend with a thin server-rendered or API-first admin/account surface, while keeping the A.S.S. launch-ticket contract explicit and testable from day one.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.x, Alembic, PostgreSQL, Pydantic, Argon2, PyOTP, Stripe SDK, PyJWT or PASETO-compatible token library, Pytest, httpx.

---

## File Structure

The new standalone repo should be created at `I:\Bosscrafts\CBCAA`.

- `I:\Bosscrafts\CBCAA\app\main.py`
  Responsibility: FastAPI app bootstrap, router registration, health routes, startup wiring.
- `I:\Bosscrafts\CBCAA\app\config.py`
  Responsibility: environment-backed settings for database, Stripe, ticket signing, hostnames, and security flags.
- `I:\Bosscrafts\CBCAA\app\db\base.py`
  Responsibility: shared SQLAlchemy declarative base.
- `I:\Bosscrafts\CBCAA\app\db\session.py`
  Responsibility: engine/session factory and FastAPI DB dependency.
- `I:\Bosscrafts\CBCAA\app\models\*.py`
  Responsibility: database models for accounts, MFA state, command-code verifier, devices, entitlements, payments, tickets, and audit events.
- `I:\Bosscrafts\CBCAA\app\schemas\*.py`
  Responsibility: API request/response models.
- `I:\Bosscrafts\CBCAA\app\auth\*.py`
  Responsibility: password hashing, login session state, TOTP setup/verify, email verification hooks.
- `I:\Bosscrafts\CBCAA\app\command_codes\*.py`
  Responsibility: validation rules and protected verification for command codes.
- `I:\Bosscrafts\CBCAA\app\devices\*.py`
  Responsibility: registration, seat enforcement, device lookup/revocation.
- `I:\Bosscrafts\CBCAA\app\entitlements\*.py`
  Responsibility: plan resolution and access checks.
- `I:\Bosscrafts\CBCAA\app\billing\*.py`
  Responsibility: Stripe checkout and webhook processing.
- `I:\Bosscrafts\CBCAA\app\tickets\*.py`
  Responsibility: signed launch-ticket issuing and replay protection.
- `I:\Bosscrafts\CBCAA\app\admin\*.py`
  Responsibility: minimal operator endpoints for support and corrections.
- `I:\Bosscrafts\CBCAA\app\audit\*.py`
  Responsibility: audit event creation/query support.
- `I:\Bosscrafts\CBCAA\migrations\`
  Responsibility: Alembic migration history.
- `I:\Bosscrafts\CBCAA\tests\`
  Responsibility: pytest coverage for all core flows.
- `I:\Bosscrafts\CBCAA\scripts\`
  Responsibility: local bootstrap, dev DB setup, and smoke helpers.
- `I:\Bosscrafts\CBCAA\deploy\`
  Responsibility: deployment manifests and environment examples.

### Task 1: Scaffold The Standalone Repo

**Files:**
- Create: `I:\Bosscrafts\CBCAA\pyproject.toml`
- Create: `I:\Bosscrafts\CBCAA\app\main.py`
- Create: `I:\Bosscrafts\CBCAA\app\config.py`
- Create: `I:\Bosscrafts\CBCAA\app\db\base.py`
- Create: `I:\Bosscrafts\CBCAA\app\db\session.py`
- Create: `I:\Bosscrafts\CBCAA\tests\test_health.py`
- Create: `I:\Bosscrafts\CBCAA\scripts\dev.ps1`

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient

from app.main import app


def test_healthcheck_returns_expected_service_contract():
    client = TestClient(app)

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "cbcaa",
        "host": "accounts.bosscrafts.net",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -q`
Expected: FAIL with `ModuleNotFoundError` or missing `app.main`.

- [ ] **Step 3: Write minimal repo bootstrap**

```python
from fastapi import FastAPI

from app.config import settings

app = FastAPI(title="CBCAA")


@app.get("/healthz")
def healthcheck() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "cbcaa",
        "host": settings.public_host,
    }
```

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CBCAA_", extra="ignore")

    public_host: str = "accounts.bosscrafts.net"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/cbcaa"
    launch_ticket_audience: str = "ass"


settings = Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_health.py -q`
Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml app tests scripts
git commit -m "feat: scaffold cbcaa service bootstrap"
```

### Task 2: Model The Core Database And Migrations

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\models\account.py`
- Create: `I:\Bosscrafts\CBCAA\app\models\device.py`
- Create: `I:\Bosscrafts\CBCAA\app\models\entitlement.py`
- Create: `I:\Bosscrafts\CBCAA\app\models\audit_event.py`
- Create: `I:\Bosscrafts\CBCAA\migrations\versions\0001_initial_core.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_models.py`

- [ ] **Step 1: Write the failing core model test**

```python
from app.models.account import Account
from app.models.device import Device
from app.models.entitlement import Entitlement


def test_core_models_expose_release_critical_fields():
    account = Account(email="boss@example.com", username="boss")
    device = Device(device_id="device-1", product_code="ass")
    entitlement = Entitlement(product_code="ass", plan_code="paid")

    assert account.email == "boss@example.com"
    assert device.product_code == "ass"
    assert entitlement.plan_code == "paid"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -q`
Expected: FAIL because model modules do not exist yet.

- [ ] **Step 3: Add the minimal SQLAlchemy models and migration**

```python
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_enrolled: Mapped[bool] = mapped_column(Boolean, default=False)
    command_code_ready: Mapped[bool] = mapped_column(Boolean, default=False)
```

```python
class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(64), index=True)
    device_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    seat_consuming: Mapped[bool] = mapped_column(Boolean, default=True)
```

```python
class Entitlement(Base):
    __tablename__ = "entitlements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    product_code: Mapped[str] = mapped_column(String(64), index=True)
    plan_code: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active")
    source: Mapped[str] = mapped_column(String(32), default="direct")
```

- [ ] **Step 4: Run tests and migration smoke check**

Run: `python -m pytest tests/test_models.py -q`
Expected: `1 passed`

Run: `python -m alembic upgrade head`
Expected: migration applies cleanly against local dev database.

- [ ] **Step 5: Commit**

```bash
git add app/models migrations tests/test_models.py
git commit -m "feat: add cbcaa core database models"
```

### Task 3: Implement Signup, Password Hashing, And Command-Code Validation

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\schemas\auth.py`
- Create: `I:\Bosscrafts\CBCAA\app\auth\passwords.py`
- Create: `I:\Bosscrafts\CBCAA\app\command_codes\service.py`
- Create: `I:\Bosscrafts\CBCAA\app\api\auth.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_signup.py`

- [ ] **Step 1: Write the failing signup contract test**

```python
def test_signup_requires_command_code_and_creates_pending_account(client):
    response = client.post(
        "/api/auth/signup",
        json={
            "email": "boss@example.com",
            "username": "boss",
            "password": "UltraSecure123!",
            "command_code": "*Alpha*codex*Bravo*ember*Gate*Signal*North",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["email"] == "boss@example.com"
    assert payload["totp_enrollment_required"] is True
    assert payload["email_verification_required"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_signup.py -q`
Expected: FAIL because `/api/auth/signup` does not exist.

- [ ] **Step 3: Implement password hashing and command-code rule enforcement**

```python
def validate_command_code(raw_code: str) -> None:
    parts = [part for part in raw_code.split("*") if part]
    if len(parts) < 7:
        raise ValueError("Command code must contain at least 7 ordered words.")
    if " " in raw_code:
        raise ValueError("Command code may not contain spaces.")
```

```python
@router.post("/signup", status_code=201, response_model=SignupResponse)
def signup(payload: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    validate_command_code(payload.command_code)
    account = create_account(
        db=db,
        email=payload.email,
        username=payload.username,
        password=payload.password,
        command_code=payload.command_code,
    )
    return SignupResponse(
        account_id=str(account.id),
        email=account.email,
        email_verification_required=True,
        totp_enrollment_required=True,
    )
```

- [ ] **Step 4: Run tests to verify the endpoint passes and weak command codes fail**

Run: `python -m pytest tests/test_signup.py -q`
Expected: signup success test passes; add a second test for a short command code returning `422` or `400`.

- [ ] **Step 5: Commit**

```bash
git add app/schemas app/auth app/command_codes app/api tests/test_signup.py
git commit -m "feat: add cbcaa signup and command code validation"
```

### Task 4: Implement TOTP Enrollment And Login Enforcement

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\auth\totp.py`
- Modify: `I:\Bosscrafts\CBCAA\app\api\auth.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_totp_login.py`

- [ ] **Step 1: Write the failing MFA test**

```python
def test_login_requires_totp_after_password_validation(client, seeded_account):
    response = client.post(
        "/api/auth/login",
        json={"identifier": "boss", "password": "UltraSecure123!"},
    )

    assert response.status_code == 200
    assert response.json()["challenge"] == "totp_required"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_totp_login.py -q`
Expected: FAIL because login flow is incomplete.

- [ ] **Step 3: Implement TOTP secret provisioning and challenge verification**

```python
def build_totp_secret() -> str:
    return pyotp.random_base32()


def verify_totp(secret: str, code: str) -> bool:
    return pyotp.TOTP(secret).verify(code, valid_window=1)
```

```python
@router.post("/login", response_model=LoginChallengeResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> LoginChallengeResponse:
    account = authenticate_primary_factor(db, payload.identifier, payload.password)
    return LoginChallengeResponse(
        challenge="totp_required",
        login_token=issue_login_token(account),
    )
```

- [ ] **Step 4: Run tests for enrollment and login challenge**

Run: `python -m pytest tests/test_totp_login.py -q`
Expected: tests cover TOTP enrollment bootstrap plus login challenge and verification success.

- [ ] **Step 5: Commit**

```bash
git add app/auth/totp.py app/api/auth.py tests/test_totp_login.py
git commit -m "feat: enforce totp login flow"
```

### Task 5: Implement Device Registration And Seat Enforcement

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\devices\service.py`
- Create: `I:\Bosscrafts\CBCAA\app\api\devices.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_devices.py`

- [ ] **Step 1: Write the failing new-device registration test**

```python
def test_new_device_registration_requires_command_code(client, verified_session):
    response = client.post(
        "/api/devices/register",
        json={
            "product_code": "ass",
            "device_id": "workstation-01",
            "device_name": "Boss Desktop",
            "command_code": "*Alpha*codex*Bravo*ember*Gate*Signal*North",
        },
        headers=verified_session,
    )

    assert response.status_code == 201
    assert response.json()["device_id"] == "workstation-01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_devices.py -q`
Expected: FAIL because device endpoint/service is missing.

- [ ] **Step 3: Implement registration and seat-count guard**

```python
def register_device(...):
    verify_command_code(account, command_code)
    enforce_seat_limit(db, account_id=account.id, product_code=product_code)
    device = Device(
        account_id=account.id,
        product_code=product_code,
        device_id=device_id,
        status="active",
        seat_consuming=True,
    )
    db.add(device)
    db.commit()
    return device
```

- [ ] **Step 4: Run tests for register, duplicate, and over-seat denial**

Run: `python -m pytest tests/test_devices.py -q`
Expected: registration succeeds; second paid-device registration fails when entitlement only allows one seat.

- [ ] **Step 5: Commit**

```bash
git add app/devices app/api/devices.py tests/test_devices.py
git commit -m "feat: add device registration and seat enforcement"
```

### Task 6: Implement Entitlement Resolution And Stripe Checkout

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\billing\service.py`
- Create: `I:\Bosscrafts\CBCAA\app\billing\webhooks.py`
- Create: `I:\Bosscrafts\CBCAA\app\api\billing.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_billing.py`

- [ ] **Step 1: Write the failing checkout test**

```python
def test_checkout_session_is_created_for_paid_ass_upgrade(client, verified_session):
    response = client.post(
        "/api/billing/checkout-sessions",
        json={"product_code": "ass", "plan_code": "paid"},
        headers=verified_session,
    )

    assert response.status_code == 201
    assert response.json()["provider"] == "stripe"
    assert response.json()["product_code"] == "ass"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_billing.py -q`
Expected: FAIL because billing endpoint is missing.

- [ ] **Step 3: Implement Stripe session creation and webhook entitlement activation**

```python
def create_checkout_session(account: Account, product_code: str, plan_code: str) -> dict[str, str]:
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url="https://accounts.bosscrafts.net/billing/success",
        cancel_url="https://accounts.bosscrafts.net/billing/cancel",
        metadata={
            "account_id": str(account.id),
            "product_code": product_code,
            "plan_code": plan_code,
        },
        line_items=[build_line_item(product_code, plan_code)],
    )
    return {"id": session.id, "url": session.url}
```

```python
def apply_checkout_completed(event: stripe.Event, db: Session) -> Entitlement:
    payload = event["data"]["object"]
    return grant_or_upgrade_entitlement(
        db=db,
        account_id=payload["metadata"]["account_id"],
        product_code=payload["metadata"]["product_code"],
        plan_code=payload["metadata"]["plan_code"],
        source="stripe",
    )
```

- [ ] **Step 4: Run tests for checkout creation and webhook-driven upgrade**

Run: `python -m pytest tests/test_billing.py -q`
Expected: mocked Stripe checkout test and webhook entitlement activation test both pass.

- [ ] **Step 5: Commit**

```bash
git add app/billing app/api/billing.py tests/test_billing.py
git commit -m "feat: add stripe billing and entitlement activation"
```

### Task 7: Implement Launch-Ticket Issuance And Replay Protection

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\tickets\service.py`
- Create: `I:\Bosscrafts\CBCAA\app\api\tickets.py`
- Create: `I:\Bosscrafts\CBCAA\tests\test_tickets.py`

- [ ] **Step 1: Write the failing launch-ticket issuance test**

```python
def test_launch_ticket_is_issued_for_entitled_registered_ass_device(client, verified_session):
    response = client.post(
        "/api/tickets/launch",
        json={"target_app": "ass", "device_id": "workstation-01"},
        headers=verified_session,
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["target_app"] == "ass"
    assert payload["expires_in_seconds"] <= 300
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_tickets.py -q`
Expected: FAIL because ticket service is not implemented.

- [ ] **Step 3: Implement signed, short-lived, replay-protected tickets**

```python
def issue_launch_ticket(account: Account, device: Device, entitlement: Entitlement) -> LaunchTicket:
    ticket_id = str(uuid.uuid4())
    expires_at = utcnow() + timedelta(minutes=5)
    token = jwt.encode(
        {
            "jti": ticket_id,
            "sub": str(account.id),
            "username": account.username,
            "target_app": "ass",
            "device_id": device.device_id,
            "tier": entitlement.plan_code,
            "exp": expires_at,
            "aud": "ass",
        },
        settings.launch_ticket_secret,
        algorithm="HS256",
    )
    persist_ticket_issue(ticket_id, account.id, device.device_id, expires_at)
    return LaunchTicket(token=token, expires_at=expires_at)
```

- [ ] **Step 4: Run tests for allowed issue, denied issue, and replay mark**

Run: `python -m pytest tests/test_tickets.py -q`
Expected: ticket issuance passes for valid account/device; invalid seat or revoked device is rejected; replay mark test passes.

- [ ] **Step 5: Commit**

```bash
git add app/tickets app/api/tickets.py tests/test_tickets.py
git commit -m "feat: add launch ticket issuance and replay protection"
```

### Task 8: Add Admin Recovery And Audit Endpoints

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\admin\service.py`
- Create: `I:\Bosscrafts\CBCAA\app\api\admin.py`
- Create: `I:\Bosscrafts\CBCAA\tests\test_admin.py`

- [ ] **Step 1: Write the failing admin correction test**

```python
def test_admin_can_manually_grant_support_license(client, admin_headers):
    response = client.post(
        "/api/admin/entitlements/grant",
        json={
            "account_id": "00000000-0000-0000-0000-000000000001",
            "product_code": "ass",
            "plan_code": "paid",
            "reason": "support correction",
        },
        headers=admin_headers,
    )

    assert response.status_code == 201
    assert response.json()["source"] == "admin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin.py -q`
Expected: FAIL because admin endpoints do not exist.

- [ ] **Step 3: Implement minimal operator endpoints and audit emission**

```python
@router.post("/entitlements/grant", status_code=201)
def grant_support_entitlement(payload: AdminGrantRequest, db: Session = Depends(get_db)):
    entitlement = grant_or_upgrade_entitlement(
        db=db,
        account_id=payload.account_id,
        product_code=payload.product_code,
        plan_code=payload.plan_code,
        source="admin",
    )
    write_audit_event(db, "entitlement.granted", actor="admin", subject_id=str(payload.account_id))
    return entitlement
```

- [ ] **Step 4: Run admin and audit tests**

Run: `python -m pytest tests/test_admin.py -q`
Expected: support grant passes; audit row exists for the action.

- [ ] **Step 5: Commit**

```bash
git add app/admin app/api/admin.py tests/test_admin.py
git commit -m "feat: add admin recovery and audit endpoints"
```

### Task 9: Wire The A.S.S. Integration Contract And Deployment Readiness

**Files:**
- Create: `I:\Bosscrafts\CBCAA\docs\ass-integration.md`
- Create: `I:\Bosscrafts\CBCAA\deploy\.env.example`
- Create: `I:\Bosscrafts\CBCAA\tests\test_ass_contract.py`
- Modify: `I:\Bosscrafts\CBCAA\app\schemas\tickets.py`

- [ ] **Step 1: Write the failing A.S.S. contract test**

```python
def test_launch_ticket_response_matches_ass_expected_fields(client, verified_session):
    response = client.post(
        "/api/tickets/launch",
        json={"target_app": "ass", "device_id": "workstation-01"},
        headers=verified_session,
    )

    payload = response.json()
    assert sorted(payload.keys()) == [
        "expires_at",
        "expires_in_seconds",
        "launch_ticket",
        "target_app",
        "ticket_id",
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ass_contract.py -q`
Expected: FAIL until the response schema is locked.

- [ ] **Step 3: Lock the response schema and document the A.S.S. flow**

```python
class LaunchTicketResponse(BaseModel):
    ticket_id: str
    launch_ticket: str
    target_app: str
    expires_at: datetime
    expires_in_seconds: int
```

```text
1. A.S.S. opens browser to https://accounts.bosscrafts.net/login
2. User completes password + TOTP
3. New device registration requires command code
4. A.S.S. requests /api/tickets/launch with target_app=ass and device_id
5. CBCAA returns short-lived signed launch ticket
6. A.S.S. exchanges ticket with local BossForgeOS handoff path
```

- [ ] **Step 4: Run the full regression set**

Run: `python -m pytest -q`
Expected: all CBCAA backend tests pass.

Run: `python -m uvicorn app.main:app --reload`
Expected: service starts locally and `/healthz` plus auth routes respond.

- [ ] **Step 5: Commit**

```bash
git add docs deploy tests app/schemas/tickets.py
git commit -m "feat: finalize ass launch ticket contract"
```

## Self-Review

Spec coverage check:
- Hosted standalone repo: covered by Tasks 1 and 9.
- Data model and migrations: covered by Task 2.
- Signup, password, command code, MFA: covered by Tasks 3 and 4.
- Device registration and enforcement: covered by Task 5.
- Stripe billing and entitlements: covered by Task 6.
- Launch tickets: covered by Task 7.
- Admin and audit: covered by Task 8.
- A.S.S. integration contract: covered by Task 9.

Placeholder scan:
- No `TODO` or `TBD` placeholders are left in task steps.

Type consistency:
- Product code uses `ass` throughout plan steps.
- Command code format stays `*Word*Word*...`.
- Launch ticket response fields are kept consistent between test and schema.
