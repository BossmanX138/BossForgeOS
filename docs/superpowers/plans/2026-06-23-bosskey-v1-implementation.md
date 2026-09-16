# Bosskey v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Bosskey v1 as a single-license USB artifact with encrypted challenge-response verification, then wire it into CBCAA, A.S.S., and BossForgeOS/Runeforge protected-action flows.

**Architecture:** Add a shared Bosskey package format and verifier in the existing `I:\Bosscrafts\CBCAA` repo, expose issuance and verification through CBCAA APIs, then teach A.S.S. to detect USB Bosskeys and present verifiable launch proof. Finally, extend BossForgeOS and Runeforge to require Bosskey for protected operational actions and Bosskey plus command code for account or user changes.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy, cryptography HMAC/AES-GCM helpers, pytest, Electron/Node.js IPC, existing CBCAA launch-ticket flow, existing Runeforge command-code gating

---

## File Structure

- `I:\Bosscrafts\CBCAA\app\models\bosskey.py`
  Responsibility: persistent Bosskey lifecycle state for one key per license.
- `I:\Bosscrafts\CBCAA\app\bosskeys\package.py`
  Responsibility: Bosskey package schema, challenge generation, response derivation, integrity validation.
- `I:\Bosscrafts\CBCAA\app\bosskeys\service.py`
  Responsibility: issuance, revocation, replacement, and challenge verification.
- `I:\Bosscrafts\CBCAA\app\schemas\bosskeys.py`
  Responsibility: Bosskey issuance/verification/admin API payloads.
- `I:\Bosscrafts\CBCAA\app\api\bosskeys.py`
  Responsibility: API routes for Bosskey issuance, challenge start, challenge verify, and admin recovery actions.
- `I:\Bosscrafts\CBCAA\app\api\auth.py`
  Responsibility: require Bosskey plus command code on account-changing auth flows.
- `I:\Bosscrafts\CBCAA\app\api\tickets.py`
  Responsibility: require recent Bosskey authorization proof before issuing A.S.S. launch tickets.
- `I:\Bosscrafts\CBCAA\app\models\__init__.py`
  Responsibility: register Bosskey model in metadata.
- `I:\Bosscrafts\CBCAA\migrations\versions\0002_add_bosskeys.py`
  Responsibility: Bosskey table migration.
- `I:\Bosscrafts\CBCAA\tests\test_bosskeys.py`
  Responsibility: Bosskey package and lifecycle tests.
- `I:\Bosscrafts\CBCAA\tests\test_ass_contract.py`
  Responsibility: A.S.S.-facing launch-ticket proof contract tests.
- `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\security\bosskey.js`
  Responsibility: USB media discovery, package read, challenge-response, local proof caching.
- `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\security\auth.js`
  Responsibility: CBCAA auth flow changes to request Bosskey proof and command code where required.
- `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\electron-main.js`
  Responsibility: IPC handlers and launch gating for Bosskey-required actions.
- `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\tests\bosskey.test.js`
  Responsibility: Node-side Bosskey USB/proof tests.
- `I:\Bosscrafts\BossForgeOS\core\security\bosskey_verifier.py`
  Responsibility: local Bosskey verification contract for BossForgeOS/Runeforge.
- `I:\Bosscrafts\BossForgeOS\core\agents\runeforge_agent.py`
  Responsibility: require Bosskey for protected operational actions and Bosskey plus command code for account/user changes.
- `I:\Bosscrafts\BossForgeOS\ui\control_hall.py`
  Responsibility: accept Bosskey-backed session context from A.S.S. handoff and expose authorization state where needed.
- `I:\Bosscrafts\BossForgeOS\tests\test_bosskey_verifier.py`
  Responsibility: BossForgeOS-side Bosskey verification tests.
- `I:\Bosscrafts\BossForgeOS\tests\test_runeforge_bosskey_policy.py`
  Responsibility: Runeforge action policy tests for Bosskey-only vs Bosskey-plus-command-code.

### Task 1: Add CBCAA Bosskey Package Format And Persistence

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\models\bosskey.py`
- Create: `I:\Bosscrafts\CBCAA\app\bosskeys\package.py`
- Modify: `I:\Bosscrafts\CBCAA\app\models\__init__.py`
- Create: `I:\Bosscrafts\CBCAA\migrations\versions\0002_add_bosskeys.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_bosskeys.py`

- [ ] **Step 1: Write the failing Bosskey package test**

```python
from app.bosskeys.package import build_bosskey_package, derive_bosskey_response


def test_bosskey_package_derives_fresh_challenge_response():
    package = build_bosskey_package(
        account_id="acct-1",
        license_id="lic-1",
        product_code="ass",
    )

    response_a = derive_bosskey_response(package.secret_material, "challenge-a")
    response_b = derive_bosskey_response(package.secret_material, "challenge-b")

    assert response_a != response_b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_bosskeys.py -q`
Expected: FAIL with missing `app.bosskeys.package`

- [ ] **Step 3: Write the minimal Bosskey package and model**

```python
@dataclass(slots=True)
class BosskeyPackage:
    package_id: str
    account_id: str
    license_id: str
    product_code: str
    secret_material: bytes
```

```python
def derive_bosskey_response(secret_material: bytes, challenge: str) -> str:
    return hmac.new(secret_material, challenge.encode("utf-8"), hashlib.sha256).hexdigest()
```

```python
class Bosskey(Base):
    __tablename__ = "bosskeys"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    license_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    product_code: Mapped[str] = mapped_column(String(64), index=True)
    package_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    encrypted_package_blob: Mapped[bytes] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(32), default="active")
```

- [ ] **Step 4: Run tests and migration smoke check**

Run: `python -m pytest tests/test_bosskeys.py -q`
Expected: PASS

Run: `python -m alembic upgrade head`
Expected: PASS and `bosskeys` table exists

- [ ] **Step 5: Commit**

```bash
git -C I:\Bosscrafts\CBCAA add app\models\bosskey.py app\bosskeys\package.py app\models\__init__.py migrations\versions\0002_add_bosskeys.py tests\test_bosskeys.py
git -C I:\Bosscrafts\CBCAA commit -m "feat: add Bosskey package format and persistence"
```

### Task 2: Add CBCAA Bosskey Issuance, Verification, And Recovery APIs

**Files:**
- Create: `I:\Bosscrafts\CBCAA\app\bosskeys\service.py`
- Create: `I:\Bosscrafts\CBCAA\app\schemas\bosskeys.py`
- Create: `I:\Bosscrafts\CBCAA\app\api\bosskeys.py`
- Modify: `I:\Bosscrafts\CBCAA\app\main.py`
- Modify: `I:\Bosscrafts\CBCAA\app\api\auth.py`
- Modify: `I:\Bosscrafts\CBCAA\app\api\tickets.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_bosskeys.py`
- Test: `I:\Bosscrafts\CBCAA\tests\test_ass_contract.py`

- [ ] **Step 1: Write the failing API test**

```python
def test_launch_ticket_requires_recent_bosskey_proof(client, access_token):
    response = client.post(
        "/api/tickets/launch",
        json={"device_id": "ass-test-device", "target_app": "bossforgeos"},
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Bosskey authorization is required."
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_ass_contract.py tests/test_bosskeys.py -q`
Expected: FAIL because Bosskey proof requirement does not exist

- [ ] **Step 3: Add minimal issuance and proof flow**

```python
def start_bosskey_challenge(db: Session, account: Account, license_id: str) -> dict[str, str]:
    challenge = secrets.token_urlsafe(24)
    verifier = hashlib.sha256(challenge.encode("utf-8")).hexdigest()
    # persist pending challenge with expiry
    return {"challenge": challenge, "package_id": bosskey.package_id}
```

```python
def verify_bosskey_challenge(...):
    expected = derive_bosskey_response(secret_material, challenge)
    if not hmac.compare_digest(expected, payload.response):
        raise HTTPException(status_code=401, detail="Bosskey challenge failed.")
```

```python
if not has_recent_bosskey_authorization(db, account.id, payload.device_id):
    raise HTTPException(status_code=403, detail="Bosskey authorization is required.")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_ass_contract.py tests/test_bosskeys.py -q`
Expected: PASS with launch-ticket gate and Bosskey challenge coverage

- [ ] **Step 5: Commit**

```bash
git -C I:\Bosscrafts\CBCAA add app\bosskeys\service.py app\schemas\bosskeys.py app\api\bosskeys.py app\main.py app\api\auth.py app\api\tickets.py tests\test_bosskeys.py tests\test_ass_contract.py
git -C I:\Bosscrafts\CBCAA commit -m "feat: add Bosskey issuance and verification APIs"
```

### Task 3: Add A.S.S. USB Detection And CBCAA Challenge-Response

**Files:**
- Create: `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\security\bosskey.js`
- Modify: `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\security\auth.js`
- Modify: `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\electron-main.js`
- Test: `I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)\tests\bosskey.test.js`

- [ ] **Step 1: Write the failing A.S.S. Bosskey test**

```javascript
const { deriveBosskeyProof } = require("../security/bosskey");

test("deriveBosskeyProof returns a response for a discovered package", async () => {
  const proof = await deriveBosskeyProof({
    packageJson: { packageId: "pkg-1", secretMaterialB64: Buffer.from("secret").toString("base64") },
    challenge: "hello",
  });

  expect(proof.packageId).toBe("pkg-1");
  expect(typeof proof.response).toBe("string");
  expect(proof.response.length).toBeGreaterThan(10);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- bosskey.test.js`
Expected: FAIL because `security/bosskey.js` does not exist

- [ ] **Step 3: Implement the minimal USB + proof helper**

```javascript
function deriveBosskeyProof({ packageJson, challenge }) {
  const secret = Buffer.from(packageJson.secretMaterialB64, "base64");
  const response = crypto.createHmac("sha256", secret).update(String(challenge), "utf8").digest("hex");
  return {
    packageId: packageJson.packageId,
    response,
  };
}
```

```javascript
async function requestBosskeyLaunchProof(session, targetApp) {
  const challengeStart = await fetchJson("/api/bosskeys/challenge/start", {...});
  const proof = await deriveBosskeyProof({...});
  return fetchJson("/api/bosskeys/challenge/verify", {...});
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `npm test -- bosskey.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git -C "I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)" add security\bosskey.js security\auth.js electron-main.js tests\bosskey.test.js
git -C "I:\Bosscrafts\Anvil Secured Shuttle (A.S.S.)" commit -m "feat: add Bosskey USB challenge flow to ass"
```

### Task 4: Add BossForgeOS Bosskey Verifier And Runeforge Policy Enforcement

**Files:**
- Create: `I:\Bosscrafts\BossForgeOS\core\security\bosskey_verifier.py`
- Modify: `I:\Bosscrafts\BossForgeOS\core\agents\runeforge_agent.py`
- Create: `I:\Bosscrafts\BossForgeOS\tests\test_bosskey_verifier.py`
- Create: `I:\Bosscrafts\BossForgeOS\tests\test_runeforge_bosskey_policy.py`

- [ ] **Step 1: Write the failing BossForgeOS verifier test**

```python
from core.security.bosskey_verifier import BosskeyAuthorization


def test_bosskey_authorization_requires_fresh_proof():
    auth = BosskeyAuthorization.from_handoff(
        {"packageId": "pkg-1", "authorizedAt": 1000, "proofScope": "operational"}
    )

    assert auth.is_fresh(now_ts=1040, max_age_seconds=60) is True
    assert auth.is_fresh(now_ts=1100, max_age_seconds=60) is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_bosskey_verifier.py tests/test_runeforge_bosskey_policy.py -q`
Expected: FAIL with missing verifier module

- [ ] **Step 3: Implement minimal verifier and policy split**

```python
@dataclass(slots=True)
class BosskeyAuthorization:
    package_id: str
    authorized_at: int
    proof_scope: str

    def is_fresh(self, now_ts: int, max_age_seconds: int = 60) -> bool:
        return now_ts - int(self.authorized_at) <= max_age_seconds
```

```python
def _bosskey_required_action_types(self) -> set[str]:
    return self._high_risk_action_types() - self._command_code_required_action_types()
```

```python
def _bosskey_plus_command_code_action_types(self) -> set[str]:
    return {
        "grant_permission",
        "revoke_permission",
        "registry_edit",
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python -m pytest tests/test_bosskey_verifier.py tests/test_runeforge_bosskey_policy.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add core\security\bosskey_verifier.py core\agents\runeforge_agent.py tests\test_bosskey_verifier.py tests\test_runeforge_bosskey_policy.py
git commit -m "feat: add Bosskey verification to BossForgeOS"
```

### Task 5: Wire A.S.S. Handoff Into Control Hall And Finalize Recovery/Audit Contract

**Files:**
- Modify: `I:\Bosscrafts\BossForgeOS\ui\control_hall.py`
- Modify: `I:\Bosscrafts\BossForgeOS\tests\test_control_hall_auth_routes.py`
- Modify: `I:\Bosscrafts\CBCAA\app\admin\service.py`
- Modify: `I:\Bosscrafts\CBCAA\tests\test_admin.py`

- [ ] **Step 1: Write the failing handoff test**

```python
def test_launch_ticket_exchange_preserves_bosskey_authorization(self):
    handoff = _encode_handoff(
        {
            "userId": "boss",
            "username": "boss",
            "roles": ["launcher.user"],
            "launchTicketId": "ticket-123",
            "targetApp": "bossforgeos",
            "ts": int(time.time()),
            "bosskey": {"packageId": "pkg-1", "authorizedAt": int(time.time()), "proofScope": "operational"},
        }
    )
```

- [ ] **Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_control_hall_auth_routes.py -q`
Expected: FAIL because Bosskey session state is not preserved

- [ ] **Step 3: Implement handoff preservation and admin recovery hooks**

```python
session["bosskey"] = handoff.get("bosskey") if isinstance(handoff.get("bosskey"), dict) else {}
```

```python
def replace_bosskey_for_license(...):
    old_bosskey.status = "replaced"
    new_bosskey.status = "active"
    write_audit_event(...)
```

- [ ] **Step 4: Run the cross-product verification suite**

Run: `python -m pytest tests/test_control_hall_auth_routes.py tests/test_bosskey_verifier.py tests/test_runeforge_bosskey_policy.py -q`
Expected: PASS

Run: `python -m pytest I:\Bosscrafts\CBCAA\tests\test_admin.py I:\Bosscrafts\CBCAA\tests\test_ass_contract.py -q`
Expected: PASS

Run: `npm test -- bosskey.test.js`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ui\control_hall.py tests\test_control_hall_auth_routes.py
git commit -m "feat: preserve Bosskey authorization in ass handoff"

git -C I:\Bosscrafts\CBCAA add app\admin\service.py tests\test_admin.py
git -C I:\Bosscrafts\CBCAA commit -m "feat: add Bosskey admin recovery flow"
```

## Self-Review

- Spec coverage:
  - USB package model: Task 1
  - challenge-response and replay resistance: Task 1, Task 2, Task 3
  - CBCAA issuance/revocation/replacement: Task 2, Task 5
  - A.S.S. launch proof: Task 2, Task 3, Task 5
  - BossForgeOS and Runeforge protected-action enforcement: Task 4, Task 5
  - Bosskey-only vs Bosskey-plus-command-code split: Task 4
- Placeholder scan:
  - No TBD/TODO steps remain
  - Each task lists exact files and executable commands
- Type consistency:
  - Shared names used consistently: `package_id`, `license_id`, `product_code`, `challenge`, `response`, `bosskey`, `proof_scope`, `authorizedAt`
