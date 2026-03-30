import unittest

from modules.os_snapshot import snapshot_all, snapshot_disk


class SnapshotTests(unittest.TestCase):
    def test_snapshot_disk_has_expected_fields(self) -> None:
        disk = snapshot_disk()
        self.assertIn("root", disk)
        self.assertIn("total_gb", disk)
        self.assertIn("used_gb", disk)
        self.assertIn("free_gb", disk)
        self.assertIn("percent", disk)

    def test_snapshot_all_contains_sections(self) -> None:
        snap = snapshot_all()
        self.assertIn("disk", snap)
        self.assertIn("docker", snap)
        self.assertIn("wsl_vhd", snap)
        self.assertIn("system", snap)
        self.assertIn("agent_load", snap)
        self.assertIn("warnings", snap)

    def test_system_section_has_memory_cpu(self) -> None:
        snap = snapshot_all()
        system = snap["system"]
        self.assertIn("cpu_percent", system)
        self.assertIn("memory", system)
        self.assertIn("swap", system)

    def test_agent_load_has_totals(self) -> None:
        snap = snapshot_all()
        load = snap["agent_load"]
        self.assertIn("tracked_processes", load)
        self.assertIn("totals", load)


if __name__ == "__main__":
    unittest.main()
