import unittest
from datetime import datetime, timedelta, timezone

from modules.agentforge.entitlements import (
    AgentForgeRuntimeContext,
    StaticEntitlementProvider,
    authorize_creation_request,
)


class AgentForgeEntitlementTests(unittest.TestCase):
    def test_unsubscribed_standalone_rejects_prime(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")

        with self.assertRaisesRegex(PermissionError, "Prime"):
            authorize_creation_request(
                context=context,
                entitlement_provider=StaticEntitlementProvider(subscribed=False),
                agent_class="prime",
                bossgate_enabled=False,
                travel_capable=False,
            )

    def test_unsubscribed_standalone_forces_local_only(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")

        decision = authorize_creation_request(
            context=context,
            entitlement_provider=StaticEntitlementProvider(subscribed=False),
            agent_class="skilled",
            bossgate_enabled=True,
            travel_capable=True,
        )

        self.assertFalse(decision["bossgate_enabled"])
        self.assertFalse(decision["travel_capable"])
        self.assertEqual(decision["creation_authority"], "standalone_local")

    def test_subscribed_standalone_allows_prime_and_travel(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")

        decision = authorize_creation_request(
            context=context,
            entitlement_provider=StaticEntitlementProvider(
                subscribed=True,
                capabilities={"agent.create.prime", "agent.create.travel"},
            ),
            agent_class="prime",
            bossgate_enabled=True,
            travel_capable=True,
        )

        self.assertTrue(decision["bossgate_enabled"])
        self.assertTrue(decision["travel_capable"])
        self.assertEqual(decision["creation_authority"], "standalone_subscribed")

    def test_expired_entitlement_is_unsubscribed(self) -> None:
        context = AgentForgeRuntimeContext(mode="standalone", installation_id="local-1")
        provider = StaticEntitlementProvider(
            subscribed=True,
            capabilities={"agent.create.prime", "agent.create.travel"},
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )

        with self.assertRaises(PermissionError):
            authorize_creation_request(
                context=context,
                entitlement_provider=provider,
                agent_class="prime",
                bossgate_enabled=True,
                travel_capable=True,
            )

    def test_integrated_mode_uses_bossforgeos_authority(self) -> None:
        context = AgentForgeRuntimeContext(mode="integrated", installation_id="bossforgeos")

        decision = authorize_creation_request(
            context=context,
            entitlement_provider=StaticEntitlementProvider(subscribed=False),
            agent_class="prime",
            bossgate_enabled=True,
            travel_capable=True,
        )

        self.assertEqual(decision["creation_authority"], "bossforgeos")
        self.assertTrue(decision["bossgate_enabled"])
        self.assertTrue(decision["travel_capable"])


if __name__ == "__main__":
    unittest.main()
