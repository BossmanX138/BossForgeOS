import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.utils import bforge


class _DummyProc:
    def __init__(self, pid: int = 4321) -> None:
        self.pid = pid


class BforgeModuleLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.runtime_path = Path(self._tmp.name) / "module_runtime.json"

    def _module_args(self, **overrides: object) -> argparse.Namespace:
        payload = {"sub": "start", "module_id": "soundforge", "standalone": False}
        payload.update(overrides)
        return argparse.Namespace(**payload)

    @patch("core.utils.bforge.pretty")
    @patch("core.utils.bforge._save_module_runtime")
    @patch("core.utils.bforge._module_runtime_path")
    @patch("core.utils.bforge._load_module_runtime")
    @patch("core.utils.bforge.subprocess.Popen")
    @patch("core.utils.bforge.ModuleRegistry")
    def test_start_rewrites_python_to_current_interpreter(
        self,
        mock_registry,
        mock_popen,
        mock_load_runtime,
        mock_runtime_path,
        mock_save_runtime,
        _mock_pretty,
    ) -> None:
        mock_runtime_path.return_value = self.runtime_path
        mock_load_runtime.return_value = {}
        mock_popen.return_value = _DummyProc(pid=2222)
        mock_registry.return_value.get.return_value = {
            "module_id": "soundforge",
            "connector_command": ["python", "-m", "modules.soundforge.connector"],
            "standalone_entrypoint": "python -m modules.soundforge.main",
        }
        mock_registry.return_value.summarize.return_value = []

        args = self._module_args(sub="start", module_id="soundforge", standalone=False)
        bforge.cmd_module(args)

        popen_cmd = mock_popen.call_args.kwargs["args"] if "args" in mock_popen.call_args.kwargs else mock_popen.call_args.args[0]
        self.assertEqual(popen_cmd[0], bforge.sys.executable)
        self.assertEqual(popen_cmd[1:], ["-m", "modules.soundforge.connector"])
        mock_save_runtime.assert_called_once()

    @patch("core.utils.bforge.pretty")
    @patch("core.utils.bforge._save_module_runtime")
    @patch("core.utils.bforge._module_runtime_path")
    @patch("core.utils.bforge._load_module_runtime")
    @patch("core.utils.bforge._pid_alive")
    @patch("core.utils.bforge.ModuleRegistry")
    def test_stop_clears_stale_runtime_entry(
        self,
        mock_registry,
        mock_pid_alive,
        mock_load_runtime,
        mock_runtime_path,
        mock_save_runtime,
        mock_pretty,
    ) -> None:
        mock_runtime_path.return_value = self.runtime_path
        mock_load_runtime.return_value = {"soundforge": {"pid": 9999}}
        mock_pid_alive.return_value = False
        mock_registry.return_value.summarize.return_value = []

        args = self._module_args(sub="stop", module_id="soundforge")
        bforge.cmd_module(args)

        saved_payload = mock_save_runtime.call_args.args[1]
        self.assertEqual(saved_payload, {})
        out = mock_pretty.call_args.args[0]
        self.assertTrue(out["ok"])
        self.assertEqual(out["message"], "module already stopped")

    def test_load_module_runtime_filters_non_dict_entries(self) -> None:
        payload = {"a": {"pid": 1}, "b": 2, "c": "x"}
        self.runtime_path.write_text(json.dumps(payload), encoding="utf-8")
        out = bforge._load_module_runtime(self.runtime_path)
        self.assertEqual(out, {"a": {"pid": 1}})

    @patch("core.utils.bforge.pretty")
    @patch("core.utils.bforge.subprocess.run")
    @patch("core.utils.bforge._pid_alive")
    @patch("core.utils.bforge._module_runtime_path")
    @patch("core.utils.bforge._load_module_runtime")
    @patch("core.utils.bforge.ModuleRegistry")
    def test_module_doctor_reports_success(
        self,
        mock_registry,
        mock_load_runtime,
        mock_runtime_path,
        mock_pid_alive,
        mock_subprocess_run,
        mock_pretty,
    ) -> None:
        mock_runtime_path.return_value = self.runtime_path
        mock_load_runtime.return_value = {"soundforge": {"pid": 3456, "started_at": "now"}}
        mock_pid_alive.return_value = True
        mock_registry.return_value.validate.return_value = {"ok": True, "modules_found": 1}
        mock_registry.return_value.summarize.return_value = [
            {
                "module_id": "soundforge",
                "standalone_entrypoint": "python -m modules.soundforge.main",
            }
        ]
        mock_subprocess_run.return_value = type("Proc", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

        args = self._module_args(sub="doctor")
        bforge.cmd_module(args)

        out = mock_pretty.call_args.args[0]
        self.assertTrue(out["ok"])
        self.assertTrue(out["smoke"]["ok"])
        self.assertEqual(out["runtime"]["modules"][0]["module_id"], "soundforge")

    @patch("core.utils.bforge.pretty")
    @patch("core.utils.bforge.subprocess.run")
    @patch("core.utils.bforge._pid_alive")
    @patch("core.utils.bforge._module_runtime_path")
    @patch("core.utils.bforge._load_module_runtime")
    @patch("core.utils.bforge.ModuleRegistry")
    def test_module_doctor_exits_nonzero_on_smoke_failure(
        self,
        mock_registry,
        mock_load_runtime,
        mock_runtime_path,
        mock_pid_alive,
        mock_subprocess_run,
        _mock_pretty,
    ) -> None:
        mock_runtime_path.return_value = self.runtime_path
        mock_load_runtime.return_value = {}
        mock_pid_alive.return_value = False
        mock_registry.return_value.validate.return_value = {"ok": True, "modules_found": 1}
        mock_registry.return_value.summarize.return_value = [
            {
                "module_id": "soundforge",
                "standalone_entrypoint": "python -m modules.soundforge.main",
            }
        ]
        mock_subprocess_run.return_value = type("Proc", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()

        args = self._module_args(sub="doctor")
        with self.assertRaises(SystemExit) as ex:
            bforge.cmd_module(args)
        self.assertEqual(ex.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
