# Prime BossGate Authentication Plan

## Supported Authentication Methods

1. **USB BossGate Key**
   - Encrypted thumbdrive containing user credentials and unique BossGate address
   - Must be present and unlocked for access
2. **RF/NFC Credential**
   - Credentials/address encoded as NFC payload or QR code
   - Scanned by phone or computer for access
3. **Authenticator App (TOTP/HOTP)**
   - User registers a TOTP/HOTP secret (e.g., Google Authenticator)
   - Generates time-based codes for login
4. **Multi-factor**
   - User may choose one or more methods at onboarding

## Credential Issuance & Management

- Only human admins (command-level) can issue new keys/credentials for others
- Standard users can only obtain credentials via:
  - Admin at Prime BossGate
  - Request terminal at Prime BossGate (with alternate verification: biometric, password, etc.)
- All credential issuance, rotation, and revocation events are logged

## Security & Privacy

- All credentials encrypted at rest (AES-256-GCM or better)
- USB/NFC credentials never stored in plaintext
- Authenticator secrets never transmitted after setup
- Revocation/rotation supported for all methods

## User Experience

- At onboarding, user selects preferred authentication method(s)
- Admin or request terminal provisions credentials
- User must present valid credential(s) for access

## Extensibility

- Support for hardware tokens (YubiKey, etc.) in future
- Support for biometric verification

## See `BossGate_Auth_stubs.py` for code stubs
