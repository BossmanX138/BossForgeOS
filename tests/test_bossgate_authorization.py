import json
import tempfile
import unittest
from pathlib import Path

from core.security.bossgate_authorization import BossGateAuthorizationRegistry


class BossGateAuthorizationRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "bossgate_human_roles.json"
        self.registry = BossGateAuthorizationRegistry(self.path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_bootstrap_owner_is_seeded_security_admin(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload["users"]["bossforge-owner"]["roles"], ["security_admin"])
        self.assertTrue(self.registry.is_seeded_security_admin("bossforge-owner"))
        self.assertTrue(self.registry.has_permission("bossforge-owner", "bossgate.roles.manage"))

    def test_multiple_roles_union_permissions(self) -> None:
        assigned = self.registry.assign_user_roles(
            acting_user="bossforge-owner",
            user_id="hybrid",
            roles=["commerce_manager", "support_engineer"],
        )
        self.assertTrue(assigned["ok"])
        permissions = self.registry.effective_permissions("hybrid")
        self.assertIn("bossgate.license.issue", permissions)
        self.assertIn("bossgate.remote_debug.open", permissions)
        self.assertIn("bossgate.map.view", permissions)

    def test_only_seeded_security_admin_can_manage_roles(self) -> None:
        self.registry.assign_user_roles("bossforge-owner", "operator-user", ["operator"])
        denied = self.registry.create_or_update_custom_role(
            acting_user="operator-user",
            role_name="auditor",
            permissions=["bossgate.map.view"],
        )
        allowed = self.registry.create_or_update_custom_role(
            acting_user="bossforge-owner",
            role_name="auditor",
            permissions=["bossgate.map.view"],
        )
        self.assertFalse(denied["ok"])
        self.assertTrue(allowed["ok"])

    def test_custom_roles_reject_unknown_permissions(self) -> None:
        result = self.registry.create_or_update_custom_role(
            acting_user="bossforge-owner",
            role_name="wildcard",
            permissions=["bossgate.everything"],
        )
        self.assertFalse(result["ok"])
        self.assertIn("unknown permissions", result["message"])

    def test_capabilities_expose_permission_driven_panels(self) -> None:
        self.registry.assign_user_roles("bossforge-owner", "multi", ["commerce_manager", "support_engineer"])
        capabilities = self.registry.capabilities_for_user("multi")
        self.assertTrue(capabilities["known_user"])
        self.assertTrue(capabilities["panels"]["bossgate_map"])
        self.assertTrue(capabilities["panels"]["commerce"])
        self.assertTrue(capabilities["panels"]["support"])
        self.assertFalse(capabilities["panels"]["security_admin"])


if __name__ == "__main__":
    unittest.main()
