import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


class InternalVLLMService:
    def __init__(
        self,
        model_path: Path,
        served_model_name: str = "runeforge_Core-7b",
        host: str = "127.0.0.1",
        port: int = 8011,
        python_exe: str | None = None,
        use_wsl: bool = False,
        wsl_distro: str = "",
        wsl_python: str = "python3",
        wsl_model_path: str = "",
    ) -> None:
        self.model_path = model_path
        self.served_model_name = served_model_name
        self.host = host
        self.port = port
        self.python_exe = python_exe or sys.executable
        self.use_wsl = use_wsl
        self.wsl_distro = wsl_distro.strip()
        self.wsl_python = (wsl_python or "python3").strip()
        self.wsl_model_path = wsl_model_path.strip()
        self.proc: subprocess.Popen[Any] | None = None
        self.last_error: str = ""

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/v1/chat/completions"

    def _check_vllm_import(self) -> tuple[bool, str]:
        probe = (
            "import importlib.util, sys; "
            "import vllm; "
            "spec = importlib.util.find_spec('vllm._C'); "
            "sys.exit(0 if spec else 21)"
        )
        cmd = self._build_python_command(["-c", probe])
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except Exception as ex:
            return False, str(ex)
        if proc.returncode != 0:
            msg = (proc.stderr or proc.stdout or "vllm import failed").strip()
            if proc.returncode == 21:
                if self.use_wsl:
                    msg = "vllm is installed in WSL runtime but native extension vllm._C is unavailable there."
                else:
                    msg = (
                        "vllm is installed but native extension vllm._C is missing in this runtime. "
                        "On Windows, use a Linux/WSL runtime for internal vLLM or provide a prebuilt compatible runtime."
                    )
            return False, msg
        return True, ""

    def _windows_path_to_wsl(self, source_path: Path) -> str:
        text = str(source_path)
        drive_match = re.match(r"^([A-Za-z]):[\\/](.*)$", text)
        if not drive_match:
            return text.replace("\\", "/")
        drive = drive_match.group(1).lower()
        tail = drive_match.group(2).replace("\\", "/")
        return f"/mnt/{drive}/{tail}"

    def _effective_model_path(self) -> str:
        if self.use_wsl:
            if self.wsl_model_path:
                return self.wsl_model_path
            return self._windows_path_to_wsl(self.model_path)
        return str(self.model_path)

    def _build_python_command(self, args: list[str]) -> list[str]:
        if not self.use_wsl:
            return [self.python_exe, *args]
        cmd: list[str] = ["wsl.exe"]
        if self.wsl_distro:
            cmd.extend(["-d", self.wsl_distro])
        cmd.extend(["--", self.wsl_python, *args])
        return cmd

    def start(self) -> dict[str, Any]:
        if self.proc is not None and self.proc.poll() is None:
            return {
                "ok": True,
                "message": "internal vllm already running",
                "pid": self.proc.pid,
                "url": self.url,
                "model": self.served_model_name,
            }

        if not self.model_path.exists():
            return {"ok": False, "message": f"model path not found: {self.model_path}"}

        ok, message = self._check_vllm_import()
        if not ok:
            return {"ok": False, "message": f"vllm is unavailable in runtime: {message}"}

        cmd = self._build_python_command([
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            self._effective_model_path(),
            "--served-model-name",
            self.served_model_name,
            "--host",
            self.host,
            "--port",
            str(self.port),
            "--disable-log-requests",
        ])

        try:
            env = os.environ.copy()
            self.proc = subprocess.Popen(cmd, env=env)
        except Exception as ex:
            self.proc = None
            self.last_error = str(ex)
            return {"ok": False, "message": f"failed to start internal vllm: {ex}"}

        return {
            "ok": True,
            "pid": self.proc.pid,
            "url": self.url,
            "model": self.served_model_name,
            "model_path": str(self.model_path),
            "command": cmd,
        }

    def stop(self) -> dict[str, Any]:
        if self.proc is None:
            return {"ok": True, "message": "internal vllm not running"}
        if self.proc.poll() is not None:
            pid = self.proc.pid
            self.proc = None
            return {"ok": True, "message": "internal vllm already stopped", "pid": pid}

        try:
            self.proc.terminate()
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        except Exception as ex:
            return {"ok": False, "message": f"failed to stop internal vllm: {ex}"}

        pid = self.proc.pid
        self.proc = None
        return {"ok": True, "message": "internal vllm stopped", "pid": pid}
