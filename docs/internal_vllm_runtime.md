# Internal vLLM Runtime Contract

This project supports a dedicated packaged runtime for internal vLLM.

## Expected Runtime Path

- Preferred interpreter:
  - `.runtime/vllm_runtime/Scripts/python.exe`
- Fallback interpreter:
  - `.venv-vllm/Scripts/python.exe`
- Explicit override:
  - `--internal-vllm-python <path>`
  - or env var `BOSSFORGE_INTERNAL_VLLM_PYTHON`

## Python Compatibility

- Runtime bootstrap expects Python `3.11` or `3.12`.
- Python `3.14` is not supported for this runtime setup.
- `setup_vllm_runtime.cmd` now auto-prefers Python 3.12 if installed.

## Windows Limitation

- Even when `vllm` installs in a Windows venv, internal startup may still fail if the native extension `vllm._C` is unavailable.
- If this occurs, run internal vLLM on a Linux/WSL runtime and pass that interpreter via `--internal-vllm-python` (or set `BOSSFORGE_INTERNAL_VLLM_PYTHON`).
- The launcher now reports this state explicitly instead of a generic import failure.

## WSL Mode

- The launcher supports a built-in WSL execution mode for internal vLLM:
  - `--internal-vllm-wsl`
  - `--internal-vllm-wsl-distro <name>` (optional)
  - `--internal-vllm-wsl-python <exe>` (default: `python3`)
  - `--internal-vllm-wsl-model-path <path>` (optional override)
- Default behavior in WSL mode:
  - uses your Windows model path and auto-converts it to `/mnt/<drive>/...` format
  - launches `python3 -m vllm.entrypoints.openai.api_server` via `wsl.exe`
  - keeps endpoint wiring unchanged (`http://127.0.0.1:8011/v1/chat/completions`)

Quick command:

- `start_bossforge_internal_vllm_wsl.cmd`
- Optional distro override:
  - `set BOSSFORGE_WSL_DISTRO=Ubuntu-24.04`
  - `start_bossforge_internal_vllm_wsl.cmd`

## One-Command Startup

- Use `start_bossforge_internal_vllm.cmd`
- This command:
  - sets `BOSSFORGE_ROOT` to the workspace
  - auto-points `BOSSFORGE_INTERNAL_VLLM_PYTHON` at `.runtime/vllm_runtime/Scripts/python.exe` when present
  - starts `launcher.bossforge_launcher`

## Internal vLLM Defaults

- Model path: `.models/runeforge_core-7b`
- Served model name: `runeforge_Core-7b`
- Endpoint: `http://127.0.0.1:8011/v1/chat/completions`

## Packaging Guidance

Ship these together for portable internal inference:

1. `.models/runeforge_core-7b/`
2. `.runtime/vllm_runtime/` (with `vllm` + compatible `torch` installed)
3. `start_bossforge_internal_vllm.cmd`
