from core.security.bosskey_verifier import BosskeyAuthorization


def test_bosskey_authorization_requires_fresh_proof():
    auth = BosskeyAuthorization.from_handoff(
        {"packageId": "pkg-1", "authorizedAt": 1000, "proofScope": "operational"}
    )

    assert auth.is_fresh(now_ts=1040, max_age_seconds=60) is True
    assert auth.is_fresh(now_ts=1100, max_age_seconds=60) is False
