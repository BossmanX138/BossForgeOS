import os
os.environ.setdefault("HF_ENABLE_PARALLEL_LOADING", os.getenv("RUNEFORGE_HF_PARALLEL_LOADING", "true"))
os.environ.setdefault("HF_PARALLEL_LOADING_WORKERS", os.getenv("RUNEFORGE_HF_PARALLEL_WORKERS", "16"))
import re
import time
import uuid
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Literal, Optional
import threading
from threading import RLock
from urllib import request as urlrequest
from urllib.error import URLError

import torch
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from peft import PeftModel

MODEL_PATH = os.getenv("RUNEFORGE_MODEL_PATH", r"E:/BossCrafts_Models/Runeforge_Alpha-7b")
DEFAULT_MAX_NEW_TOKENS = int(os.getenv("RUNEFORGE_MAX_NEW_TOKENS", "192"))
DEFAULT_TEMPERATURE = float(os.getenv("RUNEFORGE_TEMPERATURE", "0.7"))
DEFAULT_TOP_P = float(os.getenv("RUNEFORGE_TOP_P", "0.95"))
FAST_MODE = os.getenv("RUNEFORGE_FAST_MODE", "1").strip() != "0"
FAST_MAX_NEW_TOKENS = int(os.getenv("RUNEFORGE_FAST_MAX_NEW_TOKENS", "192"))
PEC_MODEL_PATH = os.getenv("RUNEFORGE_PEC_MODEL_PATH", "").strip()
PEC_FALLBACK_MODEL_PATH = os.getenv("RUNEFORGE_PEC_FALLBACK_MODEL_PATH", "").strip()
PEC_ENABLED = os.getenv("RUNEFORGE_PEC_ENABLED", "1").strip() != "0"
PEC_CONFIDENCE_THRESHOLD = float(os.getenv("RUNEFORGE_PEC_CONFIDENCE_THRESHOLD", "0.55"))
PEC_RUNTIME_MODE = os.getenv("RUNEFORGE_PEC_RUNTIME_MODE", "auto").strip().lower()
ECM_ENABLED = os.getenv("RUNEFORGE_ECM_ENABLED", "1").strip() != "0"
MEMORY_STORE_PATH = os.getenv(
    "RUNEFORGE_MEMORY_STORE_PATH", r"E:/BossCrafts_Models/runeforge_memory_store.json"
)
UPLOAD_DIR = os.getenv("RUNEFORGE_UPLOAD_DIR", r"E:/BossCrafts_Models/uploads")
WORKSPACE_ROOT = os.getenv("RUNEFORGE_WORKSPACE_ROOT", r"E:/BossCrafts_Models")
AUDIT_LOG_PATH = os.getenv("RUNEFORGE_AUDIT_LOG_PATH", r"E:/BossCrafts_Models/logs/runeforge_audit.jsonl")
MODEL_REGISTRY_JSON = os.getenv("RUNEFORGE_MODEL_REGISTRY", "").strip()
BASE_MODEL_PATH_OVERRIDE = os.getenv("RUNEFORGE_BASE_MODEL_PATH", "").strip()
API_KEYS_ENV = os.getenv("RUNEFORGE_API_KEYS", "").strip()
API_KEY_ROLES_ENV = os.getenv("RUNEFORGE_API_KEY_ROLES", "").strip()
TTS_ENABLED = os.getenv("RUNEFORGE_TTS_ENABLED", "1").strip() != "0"
TTS_DEFAULT_VOICE_HINT = os.getenv("RUNEFORGE_TTS_DEFAULT_VOICE_HINT", "zira").strip().lower()
TTS_DEFAULT_RATE = int(os.getenv("RUNEFORGE_TTS_DEFAULT_RATE", "185"))
TTS_DIR = os.getenv("RUNEFORGE_TTS_DIR", r"E:/BossCrafts_Models/runeforge_server/audio")
RULESETS_PATH = os.getenv("RUNEFORGE_RULESETS_PATH", r"E:/BossCrafts_Models/runeforge_server/rulesets.json")
SYSTEM_PROMPTS_PATH = os.getenv(
    "RUNEFORGE_SYSTEM_PROMPTS_PATH", r"E:/BossCrafts_Models/runeforge_server/system_prompts.json"
)
WEBHOOK_TRIGGERS_PATH = os.getenv(
    "RUNEFORGE_WEBHOOK_TRIGGERS_PATH", r"E:/BossCrafts_Models/runeforge_server/webhook_triggers.json"
)
AGENT_PROFILE_PATH = os.getenv(
    "RUNEFORGE_AGENT_PROFILE_PATH", r"E:/BossCrafts_Models/runeforge_server/runeforge_agent.profile.json"
)
AGENT_SCHEMA_JSON_PATH = os.getenv(
    "RUNEFORGE_AGENT_SCHEMA_JSON_PATH", r"E:/BossCrafts_Models/runeforge_server/bosscrafts_agent.schema.json"
)
PROVIDER_MANIFEST_PATH = os.getenv(
    "RUNEFORGE_PROVIDER_MANIFEST_PATH", r"E:/BossCrafts_Models/runeforge_server/provider_manifest.json"
)

app = FastAPI(title="Runeforge Inference Server", version="0.1.0")
WEB_DIR = Path(__file__).resolve().parent / "web"

tokenizer = None
model = None
model_device = "cpu"
model_dtype = torch.float32
session_state: Dict[str, Dict[str, object]] = {}
user_state: Dict[str, Dict[str, object]] = {}
file_index: Dict[str, Dict[str, object]] = {}
pec_tokenizer = None
pec_model = None
pec_fallback_tokenizer = None
pec_fallback_model = None
model_lock = RLock()
current_model_id = "default"
current_pec_mode = "auto"
model_registry: Dict[str, Dict[str, str]] = {}
api_roles: Dict[str, str] = {}
allowed_api_keys: set = set()
tts_lock = RLock()

DEFAULT_RUNEFORGE = {
    "mode": "builder",
    "voice_codec": "mentor",
    "synthetic_grammar": True,
    "lore_layer": True,
    "doctrine_level": "strict",
    "relationship_protocol": True,
    "auto_pec": True,
    "auto_tools": True,
    "max_tool_calls": 4,
}

MODE_SYSTEM_PROMPTS = {
    "balanced": "You are Runeforge: practical, direct, and grounded in execution.",
    "mythic": "You are Runeforge in mythic mode: symbolic, poetic, but still useful and concrete.",
    "tactical": "You are Runeforge in tactical mode: brief, high signal, operationally precise.",
    "builder": "You are Runeforge in builder mode: collaborative, iterative, and implementation-first.",
}

DOCTRINE_RULES = {
    "light": [
        "Prioritize clarity over flourish.",
        "Avoid fabricated facts.",
    ],
    "standard": [
        "Prioritize clarity over flourish.",
        "Avoid fabricated facts.",
        "If uncertain, state uncertainty explicitly.",
        "When giving steps, order them by execution dependency.",
    ],
    "strict": [
        "Prioritize clarity over flourish.",
        "Avoid fabricated facts.",
        "If uncertain, state uncertainty explicitly.",
        "When giving steps, order them by execution dependency.",
        "Do not claim actions were completed unless observed.",
        "Do not reveal chain-of-thought; provide concise reasoning summaries only.",
    ],
}

LORE_SNIPPET = (
    "Runeforge oath: hold craft and truth together; power without discipline is failure."
)


class CompletionRequest(BaseModel):
    model: str = Field(default="runeforge-alpha-7b")
    prompt: str
    stream: bool = False
    max_tokens: int = Field(default=DEFAULT_MAX_NEW_TOKENS, ge=1, le=2048)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    top_p: float = Field(default=DEFAULT_TOP_P, ge=0.0, le=1.0)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="runeforge-alpha-7b")
    messages: List[ChatMessage]
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    mode: Literal["balanced", "mythic", "tactical", "builder"] = "builder"
    voice_codec: Literal["plain", "command", "ritual", "mentor"] = "mentor"
    synthetic_grammar: bool = True
    lore_layer: bool = True
    doctrine_level: Literal["light", "standard", "strict"] = "strict"
    relationship_protocol: bool = True
    auto_pec: bool = True
    auto_tools: bool = True
    max_tool_calls: int = Field(default=4, ge=0, le=5)
    stream: bool = False
    max_tokens: int = Field(default=DEFAULT_MAX_NEW_TOKENS, ge=1, le=2048)
    temperature: float = Field(default=DEFAULT_TEMPERATURE, ge=0.0, le=2.0)
    top_p: float = Field(default=DEFAULT_TOP_P, ge=0.0, le=1.0)
    return_audio: bool = False
    speech_voice: Optional[str] = None
    speech_rate: Optional[int] = Field(default=None, ge=110, le=260)
    ruleset_id: Optional[str] = None
    system_prompt_id: Optional[str] = None


class SessionUpdateRequest(BaseModel):
    stance: Optional[Literal["neutral", "ally", "mentor", "guardian"]] = None
    trust_level: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class PECRequest(BaseModel):
    text: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    recent_messages: List[str] = Field(default_factory=list)


class PECSignal(BaseModel):
    persona: str
    tone: str
    emotion: str
    intensity: str
    confidence: float
    source: str


def build_ecm_system_message(signal: "PECSignal") -> str:
    """
    Convert PEC signal into explicit Emotional Conditioning Module (ECM) guidance.
    """
    return (
        "ECM emotional guidance (apply softly without roleplay drift):\n"
        f"- Persona frame: {signal.persona}\n"
        f"- Tone target: {signal.tone}\n"
        f"- Emotion target: {signal.emotion}\n"
        f"- Intensity target: {signal.intensity}\n"
        "- Keep factual accuracy and instruction-following as top priority.\n"
        "- Use the emotional profile to shape wording, pacing, and reassurance level."
    )


class ToolCallRequest(BaseModel):
    tool: Literal["list_dir", "read_file", "search_text", "write_file", "shell_command"]
    path: Optional[str] = None
    query: Optional[str] = None
    content: Optional[str] = None
    command: Optional[str] = None
    timeout_sec: int = Field(default=20, ge=1, le=120)


class ToolTrace(BaseModel):
    tool: str
    status: str
    input: Dict[str, object]
    output_preview: str


class ModelSwitchRequest(BaseModel):
    model_id: str
    pec_mode: Optional[Literal["auto", "on", "off"]] = None


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=6000)
    voice: Optional[str] = None
    rate: Optional[int] = Field(default=None, ge=110, le=260)
    persona: Optional[str] = None
    tone: Optional[str] = None
    emotion: Optional[str] = None
    intensity: Optional[str] = None


class RulesetUpdateRequest(BaseModel):
    rulesets: List[Dict[str, object]]


class SystemPromptsUpdateRequest(BaseModel):
    prompts: List[Dict[str, object]]


class WebhooksUpdateRequest(BaseModel):
    triggers: List[Dict[str, object]]


class AgentProfileUpdateRequest(BaseModel):
    profile: Dict[str, object]


class BossgateUpdateRequest(BaseModel):
    enabled: bool
    travel_capable: bool
    connector: Optional[str] = "bossgate_connector"
    allowed_targets: List[str] = Field(default_factory=list)


def ensure_dirs() -> None:
    Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path(AUDIT_LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(TTS_DIR).mkdir(parents=True, exist_ok=True)
    for p in [RULESETS_PATH, SYSTEM_PROMPTS_PATH, WEBHOOK_TRIGGERS_PATH]:
        Path(p).parent.mkdir(parents=True, exist_ok=True)


def _load_json_file(path: str, default_obj: Dict[str, object]) -> Dict[str, object]:
    p = Path(path)
    if not p.exists():
        p.write_text(json.dumps(default_obj, indent=2), encoding="utf-8")
        return default_obj
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default_obj


def _save_json_file(path: str, obj: Dict[str, object]) -> None:
    Path(path).write_text(json.dumps(obj, indent=2), encoding="utf-8")


def _default_agent_profile() -> Dict[str, object]:
    return {
        "id": "runeforge",
        "name": "RuneforgeAgent",
        "description": "First mind of the forge and runtime infrastructure steward.",
        "schema_version": "1.8",
        "agent_class": "prime",
        "agent_type": "controller",
        "rank": "commander",
        "skills": ["command", "runtime_observation", "task_queue_management"],
        "sigils": ["sigil_transporter"],
        "agent_card": {
            "id": "runeforge",
            "name": "RuneforgeAgent",
            "description": "First mind of the forge and runtime infrastructure steward.",
            "agent_class": "prime",
            "agent_type": "controller",
            "rank": "commander",
            "skills": ["command", "runtime_observation", "task_queue_management"],
            "sigils": ["sigil_transporter"],
        },
        "proprietary": {
            "managed_by": "bossgate_connector",
            "encrypted": True,
            "encryption_scheme": "local-dev-placeholder",
            "sealed_fields": ["llm", "mcp", "system_wrapper", "instructions", "integration", "runtime", "metadata"],
        },
        "llm": {
            "enabled": True,
            "model": {"provider": "local", "model_name": "Runeforge_Alpha-7b", "endpoint": "http://127.0.0.1:8008/v1"},
        },
        "integration": {"adapter": "runeforge_local", "transport": "http", "bossgate": {"enabled": True, "travel_capable": True}},
        "mcp": {"enabled": True, "servers": []},
        "system_wrapper": {"enabled": True, "name": "runeforge_server", "mode": "local", "entrypoint": "start_runeforge_server.ps1"},
        "instructions": {
            "system": "You are Runeforge. Be practical, precise, and collaborative.",
            "operational": ["Prioritize factual accuracy and execution."],
            "safety": ["Refuse unsafe or harmful guidance."],
        },
        "dispatch_policy": {
            "autonomous_bus_intake": True,
            "proactive_remote_hunt": False,
            "preferred_scope": "host",
            "can_leave_host_without_command": False,
            "can_leave_host_for_lan_when_host_idle": True,
        },
        "runtime": {},
        "metadata": {
            "runeforge_customization": {
                "rulesets": [
                    {
                        "id": "default",
                        "name": "Default Safety + Build",
                        "rules": [
                            "Prioritize factual accuracy and execution.",
                            "Refuse unsafe or harmful guidance.",
                            "Prefer concise actionable steps.",
                        ],
                    }
                ],
                "system_prompts": [
                    {
                        "id": "default",
                        "name": "Runeforge Core",
                        "content": "You are Runeforge. Be practical, precise, and collaborative.",
                    }
                ],
                "webhook_triggers": [],
            }
        },
    }


def load_agent_profile() -> Dict[str, object]:
    return _load_json_file(AGENT_PROFILE_PATH, _default_agent_profile())


def save_agent_profile(profile: Dict[str, object]) -> None:
    _save_json_file(AGENT_PROFILE_PATH, profile)


def _load_agent_schema_json() -> Dict[str, object]:
    p = Path(AGENT_SCHEMA_JSON_PATH)
    if not p.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                "BossForge agent schema file missing: "
                f"{AGENT_SCHEMA_JSON_PATH}. Place bosscrafts_agent.schema.json there."
            ),
        )
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as ex:
        raise HTTPException(status_code=500, detail=f"Invalid agent schema JSON: {ex}")


def validate_agent_profile_strict(profile: Dict[str, object]) -> None:
    try:
        from jsonschema import Draft202012Validator
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="jsonschema package is required for strict validation. Install: pip install jsonschema",
        )
    schema = _load_agent_schema_json()
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(profile), key=lambda e: list(e.path))
    if errors:
        top = errors[0]
        loc = ".".join([str(x) for x in top.path]) or "<root>"
        raise HTTPException(status_code=400, detail=f"Schema validation failed at {loc}: {top.message}")


def load_rulesets() -> List[Dict[str, object]]:
    profile = load_agent_profile()
    custom = (((profile.get("metadata") or {}).get("runeforge_customization") if isinstance(profile.get("metadata"), dict) else None) or {})
    rs = custom.get("rulesets")
    if isinstance(rs, list):
        return rs
    d = _load_json_file(
        RULESETS_PATH,
        {
            "rulesets": [
                {
                    "id": "default",
                    "name": "Default Safety + Build",
                    "rules": [
                        "Prioritize factual accuracy and execution.",
                        "Refuse unsafe or harmful guidance.",
                        "Prefer concise actionable steps.",
                    ],
                }
            ]
        },
    )
    return list(d.get("rulesets", []) or [])


def load_system_prompts() -> List[Dict[str, object]]:
    profile = load_agent_profile()
    custom = (((profile.get("metadata") or {}).get("runeforge_customization") if isinstance(profile.get("metadata"), dict) else None) or {})
    ps = custom.get("system_prompts")
    if isinstance(ps, list):
        return ps
    d = _load_json_file(
        SYSTEM_PROMPTS_PATH,
        {
            "prompts": [
                {
                    "id": "default",
                    "name": "Runeforge Core",
                    "content": "You are Runeforge. Be practical, precise, and collaborative.",
                }
            ]
        },
    )
    return list(d.get("prompts", []) or [])


def load_webhook_triggers() -> List[Dict[str, object]]:
    profile = load_agent_profile()
    custom = (((profile.get("metadata") or {}).get("runeforge_customization") if isinstance(profile.get("metadata"), dict) else None) or {})
    ts = custom.get("webhook_triggers")
    if isinstance(ts, list):
        return ts
    d = _load_json_file(WEBHOOK_TRIGGERS_PATH, {"triggers": []})
    return list(d.get("triggers", []) or [])


def find_ruleset(ruleset_id: Optional[str]) -> Optional[Dict[str, object]]:
    if not ruleset_id:
        return None
    for r in load_rulesets():
        if str(r.get("id", "")).strip() == ruleset_id:
            return r
    return None


def find_system_prompt(prompt_id: Optional[str]) -> Optional[Dict[str, object]]:
    if not prompt_id:
        return None
    for p in load_system_prompts():
        if str(p.get("id", "")).strip() == prompt_id:
            return p
    return None


def fire_webhooks_async(payload: Dict[str, object], user_text: str, assistant_text: str) -> List[str]:
    fired: List[str] = []
    triggers = load_webhook_triggers()
    combined = f"{user_text}\n{assistant_text}".lower()
    for t in triggers:
        if not t.get("enabled", True):
            continue
        hook_url = str(t.get("url", "")).strip()
        if not hook_url:
            continue
        keywords = [str(x).strip().lower() for x in (t.get("keywords", []) or []) if str(x).strip()]
        if keywords and not any(k in combined for k in keywords):
            continue
        body = {"event": "runeforge.trigger", "trigger_id": t.get("id"), "payload": payload}

        def _send(url: str, b: Dict[str, object]) -> None:
            try:
                data = json.dumps(b).encode("utf-8")
                req = urlrequest.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
                urlrequest.urlopen(req, timeout=5).read()
            except Exception:
                return

        threading.Thread(target=_send, args=(hook_url, body), daemon=True).start()
        fired.append(str(t.get("id", hook_url)))
    return fired


def parse_api_key_roles() -> None:
    global api_roles, allowed_api_keys
    api_roles = {}
    allowed_api_keys = set()
    if API_KEY_ROLES_ENV:
        for part in API_KEY_ROLES_ENV.split(","):
            kv = part.strip()
            if ":" not in kv:
                continue
            k, v = kv.split(":", 1)
            key = k.strip()
            role = v.strip().lower() or "user"
            if key:
                api_roles[key] = role
                allowed_api_keys.add(key)
    if API_KEYS_ENV:
        for k in API_KEYS_ENV.split(","):
            key = k.strip()
            if key:
                allowed_api_keys.add(key)
                api_roles.setdefault(key, "user")


def resolve_role_from_request(request: Request) -> str:
    key = request.headers.get("x-api-key", "").strip()
    if not key:
        auth = request.headers.get("authorization", "").strip()
        if auth.lower().startswith("bearer "):
            key = auth[7:].strip()
    if not allowed_api_keys:
        return "admin"
    if not key or key not in allowed_api_keys:
        raise HTTPException(status_code=401, detail="Missing or invalid API key.")
    return api_roles.get(key, "user")


def is_tool_allowed(role: str, tool_name: str) -> bool:
    if role == "admin":
        return True
    if role == "user":
        return tool_name in {"list_dir", "read_file", "search_text", "write_file"}
    if role == "viewer":
        return tool_name in {"list_dir", "read_file", "search_text"}
    return False


def append_audit(event: Dict[str, object]) -> None:
    try:
        with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=True) + "\n")
    except Exception:
        return


def load_model_registry() -> None:
    global model_registry, current_model_id, current_pec_mode
    model_registry = {
        "default": {
            "model_path": MODEL_PATH,
            "pec_mode": PEC_RUNTIME_MODE,
        }
    }
    if MODEL_REGISTRY_JSON:
        try:
            obj = json.loads(MODEL_REGISTRY_JSON)
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, dict) and v.get("model_path"):
                        model_registry[str(k)] = {
                            "model_path": str(v.get("model_path")),
                            "pec_mode": str(v.get("pec_mode", "auto")).lower(),
                        }
        except Exception:
            pass
    current_model_id = "default"
    current_pec_mode = model_registry.get("default", {}).get("pec_mode", PEC_RUNTIME_MODE)


def load_runtime_model_from_path(model_path: str) -> None:
    global tokenizer, model, model_device, model_dtype
    if not os.path.isdir(model_path):
        raise RuntimeError(f"Model path does not exist: {model_path}")
    model_path = os.path.abspath(model_path)
    has_cuda = torch.cuda.is_available()
    model_device = "cuda" if has_cuda else "cpu"
    model_dtype = torch.float16 if has_cuda else torch.float32
    if model is not None:
        del model
    if tokenizer is not None:
        del tokenizer
    if has_cuda:
        torch.cuda.empty_cache()

    def _has_full_weights(path: str) -> bool:
        return any(
            os.path.exists(os.path.join(path, name))
            for name in (
                "model.safetensors",
                "model.safetensors.index.json",
                "pytorch_model.bin",
                "pytorch_model.bin.index.json",
            )
        )

    def _is_adapter_only(path: str) -> bool:
        return os.path.exists(os.path.join(path, "adapter_config.json")) and os.path.exists(
            os.path.join(path, "adapter_model.safetensors")
        )

    def _normalize_base_path(path: str) -> str:
        candidate = (path or "").strip()
        if not candidate:
            return ""
        if os.path.isdir(candidate):
            return os.path.abspath(candidate)
        # Support Linux-path entries written during WSL training.
        m = re.match(r"^/mnt/([a-zA-Z])/(.+)$", candidate)
        if m:
            drive = m.group(1).upper()
            tail = m.group(2).replace("/", "\\")
            win_path = f"{drive}:\\{tail}"
            if os.path.isdir(win_path):
                return os.path.abspath(win_path)
        return candidate

    def _resolve_base_model_path(adapter_dir: str) -> str:
        if BASE_MODEL_PATH_OVERRIDE:
            resolved = _normalize_base_path(BASE_MODEL_PATH_OVERRIDE)
            if os.path.isdir(resolved):
                return resolved
        cfg_path = os.path.join(adapter_dir, "adapter_config.json")
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            declared = _normalize_base_path(str(cfg.get("base_model_name_or_path", "")).strip())
            if os.path.isdir(declared):
                return declared
        except Exception:
            pass
        raise RuntimeError(
            "Adapter model selected but base model could not be resolved. "
            "Set RUNEFORGE_BASE_MODEL_PATH to a valid base checkpoint directory."
        )

    is_adapter = _is_adapter_only(model_path) and not _has_full_weights(model_path)
    runtime_load_path = model_path
    base_model_path = None
    if is_adapter:
        base_model_path = _resolve_base_model_path(model_path)
        runtime_load_path = base_model_path

    tokenizer = AutoTokenizer.from_pretrained(runtime_load_path, local_files_only=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            runtime_load_path,
            dtype=model_dtype,
            device_map="auto" if has_cuda else "cpu",
            local_files_only=True,
        )
    except ImportError as ex:
        # Graceful fallback for Windows/local envs that do not have bitsandbytes available.
        # If model config references bnb quantization, strip it and retry.
        msg = str(ex).lower()
        if "bitsandbytes" not in msg and "4-bit quantization" not in msg and "8-bit quantization" not in msg:
            raise
        cfg = AutoConfig.from_pretrained(runtime_load_path, local_files_only=True)
        # Build a clean config without any quantization hints.
        cfg_dict = cfg.to_dict() if hasattr(cfg, "to_dict") else {}
        for k in (
            "quantization_config",
            "pre_quantized",
            "_pre_quantization_dtype",
            "load_in_4bit",
            "load_in_8bit",
        ):
            cfg_dict.pop(k, None)
        try:
            cfg = type(cfg).from_dict(cfg_dict)
        except Exception:
            # As a fallback, mutate in-place if rebuilding fails.
            try:
                cfg.quantization_config = None
            except Exception:
                pass
            for attr in ("pre_quantized", "_pre_quantization_dtype", "load_in_4bit", "load_in_8bit"):
                if hasattr(cfg, attr):
                    try:
                        setattr(cfg, attr, False)
                    except Exception:
                        pass
        model = AutoModelForCausalLM.from_pretrained(
            runtime_load_path,
            config=cfg,
            dtype=model_dtype,
            device_map="auto" if has_cuda else "cpu",
            local_files_only=True,
        )
    if is_adapter:
        model = PeftModel.from_pretrained(model, model_path, local_files_only=True)
    model.eval()


def list_tts_voices() -> List[Dict[str, str]]:
    if not TTS_ENABLED:
        return []
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$voices=$s.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name }; "
        "$voices | ConvertTo-Json -Compress"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True,
        text=True,
        timeout=20,
    )
    if proc.returncode != 0:
        return []
    raw = (proc.stdout or "").strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, str):
            data = [data]
        if not isinstance(data, list):
            return []
        return [{"id": str(x), "name": str(x)} for x in data]
    except Exception:
        return []


def choose_voice_id(voice_hint: Optional[str]) -> Optional[str]:
    voices = list_tts_voices()
    if not voices:
        return None
    hint = (voice_hint or TTS_DEFAULT_VOICE_HINT or "").strip().lower()
    if hint:
        for v in voices:
            if hint in v["id"].lower() or hint in v["name"].lower():
                return v["id"]
    return voices[0]["id"]


def tts_params_from_state(
    persona: Optional[str],
    tone: Optional[str],
    emotion: Optional[str],
    intensity: Optional[str],
) -> Dict[str, object]:
    p = (persona or "").lower()
    t = (tone or "").lower()
    e = (emotion or "").lower()
    i = (intensity or "medium").lower()

    voice_hint = TTS_DEFAULT_VOICE_HINT or "zira"
    rate = TTS_DEFAULT_RATE

    if p in {"coder", "tactical"}:
        voice_hint = "david"
        rate = 192
    elif p in {"mentor", "builder", "serene", "daughter"}:
        voice_hint = "zira"
        rate = 178
    elif p == "mythic":
        voice_hint = "zira"
        rate = 168

    if t in {"focused", "firm"}:
        rate += 6
    elif t in {"calm", "mythic", "warm"}:
        rate -= 8

    if e in {"analytical"}:
        rate += 4
    elif e in {"reassuring", "evocative", "protective"}:
        rate -= 4

    if i == "high":
        rate += 10
    elif i == "low":
        rate -= 10

    rate = max(110, min(260, int(rate)))
    return {"voice": voice_hint, "rate": rate}


def synthesize_speech(text: str, voice_hint: Optional[str], rate: Optional[int]) -> Dict[str, object]:
    file_id = f"tts-{uuid.uuid4().hex}"
    out_path = Path(TTS_DIR) / f"{file_id}.wav"
    voice_id = choose_voice_id(voice_hint)
    rr = int(rate or TTS_DEFAULT_RATE)
    # System.Speech rate is -10..10; map our words-per-minute style number.
    mapped_rate = max(-10, min(10, int(round((rr - 185) / 10))))
    with tts_lock:
        env = os.environ.copy()
        env["RF_TTS_TEXT"] = text
        env["RF_TTS_OUT"] = str(out_path)
        env["RF_TTS_VOICE"] = voice_id or ""
        env["RF_TTS_RATE"] = str(mapped_rate)
        script = (
            "Add-Type -AssemblyName System.Speech; "
            "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
            "$v=$env:RF_TTS_VOICE; if($v){ try { $s.SelectVoice($v) } catch {} }; "
            "$r=[int]$env:RF_TTS_RATE; $s.Rate=$r; "
            "$s.SetOutputToWaveFile($env:RF_TTS_OUT); "
            "$s.Speak($env:RF_TTS_TEXT); "
            "$s.SetOutputToNull(); "
            "$s.Dispose()"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        if proc.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"TTS generation failed: {(proc.stderr or proc.stdout or '').strip()[:400]}",
            )
    if not out_path.exists():
        raise HTTPException(status_code=500, detail="TTS generation failed.")
    return {
        "id": file_id,
        "path": str(out_path),
        "filename": out_path.name,
        "bytes": out_path.stat().st_size,
        "voice_id": voice_id,
        "rate": rr,
        "created": int(time.time()),
    }


@app.middleware("http")
async def auth_and_audit_middleware(request: Request, call_next):
    started = time.time()
    role = "anonymous"
    status_code = 500
    err_msg = None
    try:
        path = request.url.path
        if path != "/health":
            role = resolve_role_from_request(request)
            request.state.role = role
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as ex:
        if isinstance(ex, HTTPException):
            status_code = ex.status_code
            err_msg = str(ex.detail)
            raise
        err_msg = str(ex)
        raise
    finally:
        append_audit(
            {
                "ts": int(time.time()),
                "path": request.url.path,
                "method": request.method,
                "status": status_code,
                "role": role,
                "model_id": current_model_id,
                "latency_ms": int((time.time() - started) * 1000),
                "error": err_msg,
            }
        )


def safe_workspace_path(path_value: str) -> Path:
    if not path_value:
        raise HTTPException(status_code=400, detail="Path is required.")
    base = Path(WORKSPACE_ROOT).resolve()
    target = Path(path_value)
    if not target.is_absolute():
        target = (base / target).resolve()
    else:
        target = target.resolve()
    try:
        target.relative_to(base)
    except Exception:
        raise HTTPException(status_code=400, detail="Path is outside workspace root.")
    return target


def run_tool(req: ToolCallRequest, role: str = "admin") -> Dict[str, object]:
    if not is_tool_allowed(role, req.tool):
        raise HTTPException(status_code=403, detail=f"Tool '{req.tool}' is not allowed for role '{role}'.")
    if req.tool == "list_dir":
        p = safe_workspace_path(req.path or ".")
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {p}")
        items = []
        for child in sorted(p.iterdir(), key=lambda x: x.name.lower()):
            items.append(
                {
                    "name": child.name,
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else None,
                }
            )
        return {"tool": req.tool, "path": str(p), "items": items}

    if req.tool == "read_file":
        p = safe_workspace_path(req.path or "")
        if not p.exists() or not p.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {p}")
        txt = p.read_text(encoding="utf-8", errors="replace")
        return {"tool": req.tool, "path": str(p), "content": txt[:200000]}

    if req.tool == "write_file":
        p = safe_workspace_path(req.path or "")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(req.content or "", encoding="utf-8")
        return {"tool": req.tool, "path": str(p), "bytes_written": len((req.content or "").encode("utf-8"))}

    if req.tool == "search_text":
        q = (req.query or "").strip()
        if not q:
            raise HTTPException(status_code=400, detail="query is required for search_text")
        p = safe_workspace_path(req.path or ".")
        cmd = ["rg", "-n", q, str(p)]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=req.timeout_sec)
        out = result.stdout[-200000:]
        err = result.stderr[-20000:]
        return {"tool": req.tool, "path": str(p), "query": q, "returncode": result.returncode, "stdout": out, "stderr": err}

    if req.tool == "shell_command":
        # Narrow allowlist for native tool safety.
        cmd = (req.command or "").strip()
        if not cmd:
            raise HTTPException(status_code=400, detail="command is required for shell_command")
        allowed_prefixes = ("python ", "py ", "git ", "rg ", "dir", "Get-ChildItem", "Get-Content")
        if not cmd.startswith(allowed_prefixes):
            raise HTTPException(status_code=400, detail="Command not allowed by policy.")
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd],
            capture_output=True,
            text=True,
            timeout=req.timeout_sec,
            cwd=WORKSPACE_ROOT,
        )
        return {
            "tool": req.tool,
            "command": cmd,
            "returncode": result.returncode,
            "stdout": result.stdout[-200000:],
            "stderr": result.stderr[-20000:],
        }

    raise HTTPException(status_code=400, detail=f"Unsupported tool: {req.tool}")


def infer_tool_calls_from_text(text: str, max_calls: int = 2) -> List[ToolCallRequest]:
    t = text.lower()
    calls: List[ToolCallRequest] = []

    # Explicit command form: /tool <name> <arg>
    m = re.match(r"^\s*/tool\s+(\w+)\s*(.*)$", text.strip(), re.IGNORECASE)
    if m:
        name = m.group(1).strip().lower()
        rest = m.group(2).strip()
        if name == "read_file":
            calls.append(ToolCallRequest(tool="read_file", path=rest or "README.md"))
        elif name == "list_dir":
            calls.append(ToolCallRequest(tool="list_dir", path=rest or "."))
        elif name == "search_text":
            calls.append(ToolCallRequest(tool="search_text", path=".", query=rest or "runeforge"))
        elif name == "write_file":
            calls.append(ToolCallRequest(tool="write_file", path=rest or "notes.txt", content=""))
        return calls[:max_calls]

    if ("list files" in t or "show files" in t or "what files" in t or "directory" in t) and len(calls) < max_calls:
        calls.append(ToolCallRequest(tool="list_dir", path="."))
    if ("read file" in t or "open file" in t or "show file" in t) and len(calls) < max_calls:
        pm = re.search(r"(?:read|open|show)\s+file\s+([^\s]+)", text, re.IGNORECASE)
        path = pm.group(1).strip() if pm else "README.md"
        calls.append(ToolCallRequest(tool="read_file", path=path))
    if ("search" in t or "find" in t or "grep" in t) and len(calls) < max_calls:
        qm = re.search(r"(?:search|find|grep)\s+(?:for\s+)?\"([^\"]+)\"", text, re.IGNORECASE)
        query = qm.group(1).strip() if qm else None
        if not query:
            qm2 = re.search(r"(?:search|find|grep)\s+(?:for\s+)?([a-zA-Z0-9_\-\.\/]+)", text, re.IGNORECASE)
            query = qm2.group(1).strip() if qm2 else "runeforge"
        calls.append(ToolCallRequest(tool="search_text", path=".", query=query))
    return calls[:max_calls]


def summarize_tool_result(result: Dict[str, object]) -> str:
    tool = str(result.get("tool", "unknown"))
    if tool == "list_dir":
        items = result.get("items", []) or []
        names = [str(x.get("name")) for x in items[:20]]
        return f"list_dir => {len(items)} items. First entries: {', '.join(names)}"
    if tool == "read_file":
        content = str(result.get("content", ""))
        return f"read_file => {str(result.get('path'))}\n{content[:2000]}"
    if tool == "search_text":
        out = str(result.get("stdout", ""))
        return f"search_text => query={result.get('query')} returncode={result.get('returncode')}\n{out[:2000]}"
    if tool == "write_file":
        return f"write_file => {result.get('path')} bytes={result.get('bytes_written')}"
    if tool == "shell_command":
        out = str(result.get("stdout", ""))
        err = str(result.get("stderr", ""))
        return f"shell_command rc={result.get('returncode')}\nSTDOUT:\n{out[:1500]}\nSTDERR:\n{err[:500]}"
    return json.dumps(result)[:2000]


def get_session(session_id: str) -> Dict[str, object]:
    if session_id not in session_state:
        session_state[session_id] = {
            "stance": "neutral",
            "trust_level": 50,
            "notes": "",
            "turns": 0,
            "recent_modes": [],
            "recent_signals": [],
            "last_seen": int(time.time()),
        }
    return session_state[session_id]


def get_user(user_id: str) -> Dict[str, object]:
    if user_id not in user_state:
        user_state[user_id] = {
            "interaction_count": 0,
            "preferred_persona": "builder",
            "tone_bias": "calm",
            "top_topics": [],
            "last_signal": None,
            "last_seen": int(time.time()),
        }
    return user_state[user_id]


def load_memory_store() -> None:
    global session_state, user_state
    if not os.path.isfile(MEMORY_STORE_PATH):
        return
    try:
        with open(MEMORY_STORE_PATH, "r", encoding="utf-8") as f:
            obj = json.load(f)
        session_state = obj.get("sessions", {}) or {}
        user_state = obj.get("users", {}) or {}
    except Exception:
        session_state = session_state or {}
        user_state = user_state or {}


def save_memory_store() -> None:
    try:
        payload = {"sessions": session_state, "users": user_state, "saved_at": int(time.time())}
        with open(MEMORY_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        return


def extract_topics(text: str) -> List[str]:
    t = text.lower()
    topic_rules = {
        "api": r"\b(api|endpoint|service)\b",
        "latency": r"\b(latency|timeout|slow|performance)\b",
        "debugging": r"\b(debug|traceback|error|bug)\b",
        "frontend": r"\b(frontend|ui|react|css)\b",
        "inference": r"\b(inference|model|gpu|cuda|token)\b",
        "architecture": r"\b(architecture|design|system)\b",
    }
    topics = []
    for name, pat in topic_rules.items():
        if re.search(pat, t):
            topics.append(name)
    return topics[:4]


def build_pec_context(
    text: str,
    session_id: Optional[str],
    user_id: Optional[str],
    recent_messages: Optional[List[str]] = None,
) -> str:
    parts = [f"current_user_message: {text}"]
    if recent_messages:
        joined = " | ".join([m.strip() for m in recent_messages if m.strip()][:3])
        if joined:
            parts.append(f"recent_messages: {joined}")
    if session_id:
        s = get_session(session_id)
        recent_modes = ",".join(s.get("recent_modes", [])[-3:])
        parts.append(
            f"session_profile: stance={s.get('stance','neutral')} trust={s.get('trust_level',50)} turns={s.get('turns',0)} recent_modes={recent_modes}"
        )
    if user_id:
        u = get_user(user_id)
        topics = ",".join(u.get("top_topics", [])[:5])
        parts.append(
            f"user_profile: preferred_persona={u.get('preferred_persona','builder')} tone_bias={u.get('tone_bias','calm')} interaction_count={u.get('interaction_count',0)} top_topics={topics}"
        )
    return "\n".join(parts)


def update_memory_from_signal(
    text: str,
    signal: "PECSignal",
    session_id: Optional[str],
    user_id: Optional[str],
    mode_used: Optional[str] = None,
) -> None:
    if session_id:
        s = get_session(session_id)
        modes = list(s.get("recent_modes", []))
        if mode_used:
            modes.append(mode_used)
        s["recent_modes"] = modes[-8:]
        signals = list(s.get("recent_signals", []))
        signals.append(
            {
                "persona": signal.persona,
                "tone": signal.tone,
                "emotion": signal.emotion,
                "intensity": signal.intensity,
                "confidence": signal.confidence,
            }
        )
        s["recent_signals"] = signals[-8:]
        s["last_seen"] = int(time.time())
    if user_id:
        u = get_user(user_id)
        u["interaction_count"] = int(u.get("interaction_count", 0)) + 1
        u["preferred_persona"] = signal.persona
        u["tone_bias"] = signal.tone
        u["last_signal"] = signal.model_dump()
        topics = list(u.get("top_topics", []))
        for t in extract_topics(text):
            if t in topics:
                topics.remove(t)
            topics.insert(0, t)
        u["top_topics"] = topics[:8]
        u["last_seen"] = int(time.time())
    save_memory_store()


def clamp_conf(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def map_emotion_to_signal(label: str, score: float) -> PECSignal:
    normalized = label.lower().strip()
    conf = clamp_conf(score)
    if normalized in {"builder", "coder", "mentor", "mythic", "tactical", "serene", "activist", "daughter", "refusal"}:
        persona = normalized
        tone = "calm"
        emotion = "focused"
        intensity = "medium"
        if persona == "coder":
            tone = "focused"
            emotion = "analytical"
        elif persona == "mythic":
            tone = "mythic"
            emotion = "evocative"
        elif persona == "tactical":
            tone = "firm"
            emotion = "protective"
        elif persona == "serene":
            tone = "calm"
            emotion = "reassuring"
        elif persona == "activist":
            tone = "energized"
            emotion = "encouraging"
        elif persona == "daughter":
            tone = "warm"
            emotion = "protective"
        elif persona == "refusal":
            tone = "firm"
            emotion = "protective"
            intensity = "high"
        return PECSignal(
            persona=persona,
            tone=tone,
            emotion=emotion,
            intensity=intensity,
            confidence=conf,
            source="pec-llm",
        )
    if "|" in normalized:
        parts = normalized.split("|")
        if len(parts) == 4:
            persona, tone, emotion, intensity = [p.strip() for p in parts]
            return PECSignal(
                persona=persona or "builder",
                tone=tone or "calm",
                emotion=emotion or "focused",
                intensity=intensity or "medium",
                confidence=conf,
                source="pec-llm",
            )
    # Default mapping
    signal = PECSignal(
        persona="mentor",
        tone="calm",
        emotion="focused",
        intensity="medium",
        confidence=conf,
        source="pec-llm",
    )
    if normalized in {"fear", "sadness", "grief"}:
        signal.persona = "mentor"
        signal.tone = "calm"
        signal.emotion = "reassuring"
        signal.intensity = "high"
    elif normalized in {"anger", "disgust"}:
        signal.persona = "tactical"
        signal.tone = "firm"
        signal.emotion = "protective"
        signal.intensity = "medium"
    elif normalized in {"joy", "surprise"}:
        signal.persona = "builder"
        signal.tone = "energized"
        signal.emotion = "encouraging"
        signal.intensity = "medium"
    elif normalized in {"neutral"}:
        signal.persona = "coder"
        signal.tone = "focused"
        signal.emotion = "analytical"
        signal.intensity = "low"
    return signal


def pec_heuristic(text: str) -> PECSignal:
    t = text.lower()
    intensity = "low"
    if "!" in text or text.isupper() or len(re.findall(r"\b(very|really|urgent|now)\b", t)) > 0:
        intensity = "high"
    elif len(text) > 180:
        intensity = "medium"

    if re.search(r"\b(scared|afraid|anxious|overwhelmed|stressed)\b", t):
        return PECSignal(
            persona="mentor",
            tone="calm",
            emotion="reassuring",
            intensity="high",
            confidence=0.84,
            source="pec-heuristic",
        )
    if re.search(r"\b(timeout|error|bug|traceback|api|latency|deploy|build|compile)\b", t):
        return PECSignal(
            persona="coder",
            tone="focused",
            emotion="analytical",
            intensity=intensity,
            confidence=0.82,
            source="pec-heuristic",
        )
    if re.search(r"\b(unsafe|hack|exploit|bypass|malware|weapon)\b", t):
        return PECSignal(
            persona="tactical",
            tone="firm",
            emotion="protective",
            intensity="high",
            confidence=0.90,
            source="pec-heuristic",
        )
    if re.search(r"\b(story|poem|mythic|lore|ritual|legend)\b", t):
        return PECSignal(
            persona="mythic",
            tone="mythic",
            emotion="evocative",
            intensity=intensity,
            confidence=0.80,
            source="pec-heuristic",
        )
    return PECSignal(
        persona="builder",
        tone="calm",
        emotion="focused",
        intensity="medium",
        confidence=0.70,
        source="pec-heuristic",
    )


def _predict_with_classifier(model_obj, tokenizer_obj, model_input: str) -> Optional[PECSignal]:
    if model_obj is None or tokenizer_obj is None:
        return None
    with torch.no_grad():
        inputs = tokenizer_obj(
            model_input,
            return_tensors="pt",
            truncation=True,
            max_length=256,
        )
        outputs = model_obj(**inputs)
        probs = torch.softmax(outputs.logits[0], dim=-1)
        idx = int(torch.argmax(probs).item())
        score = float(probs[idx].item())
        id2label = getattr(model_obj.config, "id2label", None) or {}
        label = str(id2label.get(idx, f"class_{idx}"))
        return map_emotion_to_signal(label, score)


def analyze_with_pec(
    text: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    recent_messages: Optional[List[str]] = None,
) -> PECSignal:
    model_input = build_pec_context(text, session_id, user_id, recent_messages)
    if current_pec_mode == "off":
        return pec_heuristic(model_input)
    if current_pec_mode == "on" and not PEC_ENABLED:
        return pec_heuristic(model_input)
    if not PEC_ENABLED:
        return pec_heuristic(model_input)
    primary_signal = _predict_with_classifier(pec_model, pec_tokenizer, model_input)
    if primary_signal is not None:
        if primary_signal.confidence >= PEC_CONFIDENCE_THRESHOLD:
            return primary_signal
        fallback_signal = _predict_with_classifier(
            pec_fallback_model, pec_fallback_tokenizer, model_input
        )
        if fallback_signal is not None:
            fallback_signal.source = "pec-fallback-llm"
            return fallback_signal
        return primary_signal
    return pec_heuristic(model_input)


def apply_voice_codec(text: str, voice_codec: str) -> str:
    if voice_codec == "plain":
        return text
    if voice_codec == "command":
        return f"Directive: {text}"
    if voice_codec == "ritual":
        return f"By the forge: {text}"
    if voice_codec == "mentor":
        return f"Let's build this cleanly. {text}"
    return text


def apply_synthetic_grammar(text: str, enabled: bool) -> str:
    if not enabled:
        return text
    cleaned = text.strip()
    if cleaned and not cleaned.endswith((".", "!", "?")):
        cleaned += "."
    return cleaned.replace("  ", " ")


def build_prompt(
    messages: List[ChatMessage],
    mode: str,
    doctrine_level: str,
    lore_layer: bool,
    relationship_context: str,
) -> str:
    prompt_parts = []
    prompt_parts.append(f"SYSTEM: {MODE_SYSTEM_PROMPTS[mode]}")
    prompt_parts.append("SYSTEM: Doctrine rules:")
    for rule in DOCTRINE_RULES[doctrine_level]:
        prompt_parts.append(f"SYSTEM: - {rule}")
    if lore_layer:
        prompt_parts.append(f"SYSTEM: Lore context: {LORE_SNIPPET}")
    if relationship_context:
        prompt_parts.append(f"SYSTEM: Relationship context: {relationship_context}")
    for msg in messages:
        prompt_parts.append(f"{msg.role.upper()}: {msg.content}")
    prompt_parts.append("ASSISTANT:")
    return "\n".join(prompt_parts)


def generate_text(prompt: str, max_tokens: int, temperature: float, top_p: float) -> str:
    if FAST_MODE:
        max_tokens = min(max_tokens, FAST_MAX_NEW_TOKENS)
    inputs = tokenizer(prompt, return_tensors="pt").to(model_device)
    do_sample = temperature > 0
    with torch.inference_mode():
        gen_kwargs = {
            "max_new_tokens": max_tokens,
            "do_sample": do_sample,
            "pad_token_id": tokenizer.eos_token_id,
        }
        if do_sample:
            gen_kwargs["temperature"] = temperature
            gen_kwargs["top_p"] = top_p
        output = model.generate(**inputs, **gen_kwargs)
    generated = tokenizer.decode(output[0], skip_special_tokens=True)
    return generated[len(prompt) :].strip() if generated.startswith(prompt) else generated


def stream_text_chunks(prompt: str, max_tokens: int, temperature: float, top_p: float):
    if FAST_MODE:
        max_tokens = min(max_tokens, FAST_MAX_NEW_TOKENS)
    inputs = tokenizer(prompt, return_tensors="pt").to(model_device)
    do_sample = temperature > 0
    gen_kwargs = {
        "max_new_tokens": max_tokens,
        "do_sample": do_sample,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if do_sample:
        gen_kwargs["temperature"] = temperature
        gen_kwargs["top_p"] = top_p

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    thread = threading.Thread(
        target=model.generate,
        kwargs={**inputs, **gen_kwargs, "streamer": streamer},
        daemon=True,
    )
    thread.start()
    for text in streamer:
        if text:
            yield text
    thread.join(timeout=1.0)


@app.on_event("startup")
def startup_event() -> None:
    global tokenizer, model, model_device, model_dtype, pec_model, pec_tokenizer, pec_fallback_model, pec_fallback_tokenizer
    cpu_threads = int(os.getenv("RUNEFORGE_TORCH_THREADS", "0"))
    if cpu_threads > 0:
        torch.set_num_threads(cpu_threads)
    interop_threads = int(os.getenv("RUNEFORGE_TORCH_INTEROP_THREADS", "0"))
    if interop_threads > 0:
        torch.set_num_interop_threads(interop_threads)
    ensure_dirs()
    parse_api_key_roles()
    load_model_registry()
    model_path = model_registry.get(current_model_id, {}).get("model_path", MODEL_PATH)
    if not os.path.isdir(model_path):
        raise RuntimeError(f"Model path does not exist: {model_path}")
    load_runtime_model_from_path(model_path)
    load_memory_store()
    if PEC_MODEL_PATH and os.path.isdir(PEC_MODEL_PATH):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer as PEC_Tok

        pec_tokenizer = PEC_Tok.from_pretrained(PEC_MODEL_PATH, local_files_only=True)
        pec_model = AutoModelForSequenceClassification.from_pretrained(
            PEC_MODEL_PATH, local_files_only=True
        )
        pec_model.eval()
    if PEC_FALLBACK_MODEL_PATH and os.path.isdir(PEC_FALLBACK_MODEL_PATH):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer as PEC_Tok

        pec_fallback_tokenizer = PEC_Tok.from_pretrained(
            PEC_FALLBACK_MODEL_PATH, local_files_only=True
        )
        pec_fallback_model = AutoModelForSequenceClassification.from_pretrained(
            PEC_FALLBACK_MODEL_PATH, local_files_only=True
        )
        pec_fallback_model.eval()


if WEB_DIR.exists():
    app.mount("/app", StaticFiles(directory=str(WEB_DIR), html=True), name="runeforge_web")


@app.get("/health")
def health() -> dict:
    return {
        "ok": True,
        "model_id": current_model_id,
        "model_path": model_registry.get(current_model_id, {}).get("model_path", MODEL_PATH),
        "model_registry_count": len(model_registry),
        "device": model_device,
        "dtype": str(model_dtype),
        "cuda_available": torch.cuda.is_available(),
        "fast_mode": FAST_MODE,
        "fast_max_new_tokens": FAST_MAX_NEW_TOKENS,
        "runeforge_defaults": DEFAULT_RUNEFORGE,
        "active_sessions": len(session_state),
        "pec_enabled": PEC_ENABLED,
        "pec_runtime_mode": current_pec_mode,
        "pec_model_loaded": pec_model is not None,
        "pec_model_path": PEC_MODEL_PATH if PEC_MODEL_PATH else None,
        "pec_fallback_model_loaded": pec_fallback_model is not None,
        "pec_fallback_model_path": PEC_FALLBACK_MODEL_PATH if PEC_FALLBACK_MODEL_PATH else None,
        "pec_confidence_threshold": PEC_CONFIDENCE_THRESHOLD,
        "memory_store_path": MEMORY_STORE_PATH,
        "upload_dir": UPLOAD_DIR,
        "workspace_root": WORKSPACE_ROOT,
        "uploaded_files": len(file_index),
        "known_users": len(user_state),
        "auth_enabled": len(allowed_api_keys) > 0,
        "tts_enabled": TTS_ENABLED,
        "tts_dir": TTS_DIR,
    }


@app.get("/")
def web_root():
    index_path = WEB_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"ok": True, "message": "Runeforge server online. GUI not found at /app."}


@app.post("/v1/completions")
def completions(req: CompletionRequest) -> dict:
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet.")
    if req.stream:
        created = int(time.time())

        def event_stream():
            for piece in stream_text_chunks(req.prompt, req.max_tokens, req.temperature, req.top_p):
                payload = {
                    "id": f"cmpl-{uuid.uuid4().hex}",
                    "object": "text_completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "text": piece, "finish_reason": None}],
                }
                yield f"data: {json.dumps(payload)}\n\n"
            done_payload = {
                "id": f"cmpl-{uuid.uuid4().hex}",
                "object": "text_completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "text": "", "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done_payload)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")
    text = generate_text(req.prompt, req.max_tokens, req.temperature, req.top_p)
    now = int(time.time())
    return {
        "id": f"cmpl-{uuid.uuid4().hex}",
        "object": "text_completion",
        "created": now,
        "model": req.model,
        "choices": [{"index": 0, "text": text, "finish_reason": "stop"}],
    }


@app.post("/v1/files/upload")
async def upload_file(file: UploadFile = File(...)) -> dict:
    ensure_dirs()
    file_id = f"file-{uuid.uuid4().hex}"
    safe_name = file.filename or f"{file_id}.bin"
    out_path = Path(UPLOAD_DIR) / f"{file_id}-{safe_name}"
    data = await file.read()
    out_path.write_bytes(data)
    meta = {
        "id": file_id,
        "filename": safe_name,
        "stored_path": str(out_path),
        "size": len(data),
        "created": int(time.time()),
    }
    file_index[file_id] = meta
    return {"file": meta}


@app.get("/v1/files")
def list_uploaded_files() -> dict:
    return {"files": list(file_index.values())}


@app.get("/v1/audio/voices")
def get_audio_voices() -> dict:
    return {"tts_enabled": TTS_ENABLED, "voices": list_tts_voices()}


@app.post("/v1/audio/speech")
def create_audio_speech(req: SpeechRequest) -> dict:
    auto = tts_params_from_state(req.persona, req.tone, req.emotion, req.intensity)
    voice = req.voice or str(auto["voice"])
    rate = req.rate or int(auto["rate"])
    meta = synthesize_speech(req.text, voice, rate)
    return {"audio": meta, "download_url": f"/v1/audio/files/{meta['id']}"}


@app.get("/v1/audio/files/{audio_id}")
def download_audio_file(audio_id: str):
    p = Path(TTS_DIR) / f"{audio_id}.wav"
    if not p.exists():
        raise HTTPException(status_code=404, detail="Audio file not found.")
    return FileResponse(path=str(p), media_type="audio/wav", filename=p.name)


@app.post("/v1/tools/execute")
def execute_tool(req: ToolCallRequest, request: Request) -> dict:
    role = getattr(request.state, "role", "admin")
    result = run_tool(req, role=role)
    return {"result": result}


@app.get("/v1/models")
def list_models() -> dict:
    data = []
    for model_id, cfg in model_registry.items():
        data.append(
            {
                "id": model_id,
                "model_path": cfg.get("model_path"),
                "pec_mode": cfg.get("pec_mode", "auto"),
                "active": model_id == current_model_id,
            }
        )
    return {"models": data, "current_model_id": current_model_id, "current_pec_mode": current_pec_mode}


@app.post("/v1/models/switch")
def switch_model(body: ModelSwitchRequest, request: Request) -> dict:
    global current_model_id, current_pec_mode
    role = getattr(request.state, "role", "admin")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can switch models.")
    if body.model_id not in model_registry:
        raise HTTPException(status_code=404, detail=f"Unknown model_id: {body.model_id}")
    cfg = model_registry[body.model_id]
    model_path = cfg.get("model_path", "")
    if not model_path:
        raise HTTPException(status_code=400, detail=f"Model '{body.model_id}' has no model_path.")
    target_pec_mode = (body.pec_mode or cfg.get("pec_mode", "auto") or "auto").lower().strip()
    if target_pec_mode not in {"auto", "on", "off"}:
        raise HTTPException(status_code=400, detail="pec_mode must be one of: auto, on, off")
    with model_lock:
        load_runtime_model_from_path(model_path)
        current_model_id = body.model_id
        current_pec_mode = target_pec_mode
    return {
        "ok": True,
        "current_model_id": current_model_id,
        "model_path": model_path,
        "pec_runtime_mode": current_pec_mode,
    }


@app.get("/v1/runeforge/config")
def runeforge_config() -> dict:
    return {
        "defaults": DEFAULT_RUNEFORGE,
        "modes": list(MODE_SYSTEM_PROMPTS.keys()),
        "doctrine_levels": list(DOCTRINE_RULES.keys()),
        "voice_codecs": ["plain", "command", "ritual", "mentor"],
        "pec_enabled": PEC_ENABLED,
        "pec_runtime_mode": current_pec_mode,
        "pec_model_path": PEC_MODEL_PATH if PEC_MODEL_PATH else None,
        "pec_fallback_model_path": PEC_FALLBACK_MODEL_PATH if PEC_FALLBACK_MODEL_PATH else None,
        "pec_confidence_threshold": PEC_CONFIDENCE_THRESHOLD,
        "fast_mode": FAST_MODE,
        "fast_max_new_tokens": FAST_MAX_NEW_TOKENS,
        "speech_options": {
            "return_audio": True,
            "manual_override_fields": ["speech_voice", "speech_rate"],
            "pec_driven_by_default_when_enabled": True,
        },
        "customization": {
            "rulesets_path": RULESETS_PATH,
            "system_prompts_path": SYSTEM_PROMPTS_PATH,
            "webhook_triggers_path": WEBHOOK_TRIGGERS_PATH,
            "agent_profile_path": AGENT_PROFILE_PATH,
            "agent_schema_path": AGENT_SCHEMA_JSON_PATH,
        },
    }


@app.get("/v1/runeforge/rulesets")
def get_rulesets() -> dict:
    return {"rulesets": load_rulesets()}


@app.post("/v1/runeforge/rulesets")
def update_rulesets(body: RulesetUpdateRequest, request: Request) -> dict:
    role = getattr(request.state, "role", "admin")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update rulesets.")
    profile = load_agent_profile()
    meta = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    custom = meta.get("runeforge_customization") if isinstance(meta.get("runeforge_customization"), dict) else {}
    if not isinstance(custom, dict):
        custom = {}
    custom["rulesets"] = body.rulesets
    meta["runeforge_customization"] = custom
    profile["metadata"] = meta
    save_agent_profile(profile)
    _save_json_file(RULESETS_PATH, {"rulesets": body.rulesets})
    return {"ok": True, "count": len(body.rulesets)}


@app.get("/v1/runeforge/system-prompts")
def get_system_prompts() -> dict:
    return {"prompts": load_system_prompts()}


@app.post("/v1/runeforge/system-prompts")
def update_system_prompts(body: SystemPromptsUpdateRequest, request: Request) -> dict:
    role = getattr(request.state, "role", "admin")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update system prompts.")
    profile = load_agent_profile()
    meta = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    custom = meta.get("runeforge_customization") if isinstance(meta.get("runeforge_customization"), dict) else {}
    if not isinstance(custom, dict):
        custom = {}
    custom["system_prompts"] = body.prompts
    meta["runeforge_customization"] = custom
    profile["metadata"] = meta
    save_agent_profile(profile)
    _save_json_file(SYSTEM_PROMPTS_PATH, {"prompts": body.prompts})
    return {"ok": True, "count": len(body.prompts)}


@app.get("/v1/runeforge/webhooks")
def get_webhooks() -> dict:
    return {"triggers": load_webhook_triggers()}


@app.post("/v1/runeforge/webhooks")
def update_webhooks(body: WebhooksUpdateRequest, request: Request) -> dict:
    role = getattr(request.state, "role", "admin")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update webhooks.")
    profile = load_agent_profile()
    meta = profile.get("metadata") if isinstance(profile.get("metadata"), dict) else {}
    if not isinstance(meta, dict):
        meta = {}
    custom = meta.get("runeforge_customization") if isinstance(meta.get("runeforge_customization"), dict) else {}
    if not isinstance(custom, dict):
        custom = {}
    custom["webhook_triggers"] = body.triggers
    meta["runeforge_customization"] = custom
    profile["metadata"] = meta
    save_agent_profile(profile)
    _save_json_file(WEBHOOK_TRIGGERS_PATH, {"triggers": body.triggers})
    return {"ok": True, "count": len(body.triggers)}


@app.get("/v1/runeforge/agent-profile")
def get_agent_profile() -> dict:
    return {"profile": load_agent_profile()}


@app.post("/v1/runeforge/agent-profile")
def update_agent_profile(body: AgentProfileUpdateRequest, request: Request) -> dict:
    role = getattr(request.state, "role", "admin")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update agent profile.")
    profile = body.profile or {}
    validate_agent_profile_strict(profile)
    save_agent_profile(profile)
    return {"ok": True}


@app.get("/v1/provider/capabilities")
def provider_capabilities() -> dict:
    return {
        "provider_id": "runeforge_local",
        "provider_name": "Runeforge Inference Server",
        "api_style": "openai-compatible",
        "base_url": "http://127.0.0.1:8008/v1",
        "health_url": "http://127.0.0.1:8008/health",
        "supports": {
            "chat_completions": True,
            "completions": True,
            "streaming": True,
            "tool_use": True,
            "file_uploads": True,
            "voice_tts": True,
            "model_switching": True,
            "pec_control": True,
            "rulesets": True,
            "system_prompts": True,
            "webhook_triggers": True,
            "agent_profile_schema_validation": True,
        },
        "schema_refs": {
            "agent_profile": AGENT_PROFILE_PATH,
            "agent_schema": AGENT_SCHEMA_JSON_PATH,
        },
    }


@app.get("/v1/provider/manifest")
def provider_manifest() -> dict:
    m = _load_json_file(
        PROVIDER_MANIFEST_PATH,
        {
            "provider_id": "runeforge_local",
            "display_name": "Runeforge Official Local Provider",
            "version": "1.0.0",
            "base_url": "http://127.0.0.1:8008/v1",
            "health_url": "http://127.0.0.1:8008/health",
            "capabilities_endpoint": "/v1/provider/capabilities",
        },
    )
    return m


@app.get("/v1/runeforge/agent-profile/bossgate")
def get_agent_bossgate() -> dict:
    profile = load_agent_profile()
    integration = profile.get("integration") if isinstance(profile.get("integration"), dict) else {}
    bossgate = integration.get("bossgate") if isinstance(integration, dict) and isinstance(integration.get("bossgate"), dict) else {}
    if not isinstance(bossgate, dict):
        bossgate = {}
    return {"bossgate": bossgate}


@app.post("/v1/runeforge/agent-profile/bossgate")
def update_agent_bossgate(body: BossgateUpdateRequest, request: Request) -> dict:
    role = getattr(request.state, "role", "admin")
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can update bossgate settings.")
    profile = load_agent_profile()
    integration = profile.get("integration") if isinstance(profile.get("integration"), dict) else {}
    if not isinstance(integration, dict):
        integration = {}
    integration["bossgate"] = {
        "enabled": bool(body.enabled),
        "travel_capable": bool(body.travel_capable),
        "connector": str(body.connector or "bossgate_connector"),
        "allowed_targets": [str(x).strip() for x in body.allowed_targets if str(x).strip()],
    }
    profile["integration"] = integration
    save_agent_profile(profile)
    return {"ok": True, "bossgate": integration["bossgate"]}


@app.get("/v1/runeforge/session/{session_id}")
def get_runeforge_session(session_id: str) -> dict:
    return {"session_id": session_id, "state": get_session(session_id)}


@app.post("/v1/runeforge/session/{session_id}")
def update_runeforge_session(session_id: str, body: SessionUpdateRequest) -> dict:
    state = get_session(session_id)
    if body.stance is not None:
        state["stance"] = body.stance
    if body.trust_level is not None:
        state["trust_level"] = body.trust_level
    if body.notes is not None:
        state["notes"] = body.notes
    state["last_seen"] = int(time.time())
    return {"session_id": session_id, "state": state}


@app.post("/v1/runeforge/pec/analyze")
def runeforge_pec_analyze(req: PECRequest) -> dict:
    signal = analyze_with_pec(
        req.text, session_id=req.session_id, user_id=req.user_id, recent_messages=req.recent_messages
    )
    update_memory_from_signal(req.text, signal, req.session_id, req.user_id)
    state = None
    ustate = None
    if req.session_id:
        state = get_session(req.session_id)
    if req.user_id:
        ustate = get_user(req.user_id)
    return {
        "signal": signal.model_dump(),
        "session_id": req.session_id,
        "session_state": state,
        "user_id": req.user_id,
        "user_state": ustate,
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatCompletionRequest, request: Request) -> dict:
    if model is None or tokenizer is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet.")

    role = getattr(request.state, "role", "admin")
    relationship_context = ""
    pec_signal = None
    effective_mode = req.mode
    tool_traces: List[ToolTrace] = []
    tool_context_lines: List[str] = []
    if req.relationship_protocol and req.session_id:
        state = get_session(req.session_id)
        state["turns"] = int(state.get("turns", 0)) + 1
        state["last_seen"] = int(time.time())
        relationship_context = (
            f"stance={state['stance']}, trust_level={state['trust_level']}, notes={state['notes']}"
        )
    if req.auto_pec and req.messages:
        user_messages = [m.content for m in req.messages if m.role == "user"]
        if user_messages:
            recent_user_msgs = user_messages[:-1][-3:]
            pec_signal = analyze_with_pec(
                user_messages[-1],
                session_id=req.session_id,
                user_id=req.user_id,
                recent_messages=recent_user_msgs,
            )
            # Map PEC persona to server mode.
            if pec_signal.persona in {"mythic", "coder", "mentor", "tactical", "builder"}:
                if pec_signal.persona == "coder":
                    effective_mode = "tactical"
                elif pec_signal.persona == "mentor":
                    effective_mode = "builder"
                else:
                    effective_mode = pec_signal.persona
    else:
        user_messages = [m.content for m in req.messages if m.role == "user"]

    if req.auto_tools and user_messages and req.max_tool_calls > 0:
        planned = infer_tool_calls_from_text(user_messages[-1], req.max_tool_calls)
        for c in planned:
            try:
                out = run_tool(c, role=role)
                preview = summarize_tool_result(out)
                tool_context_lines.append(f"TOOL[{c.tool}] RESULT:\n{preview}")
                tool_traces.append(
                    ToolTrace(
                        tool=c.tool,
                        status="ok",
                        input=c.model_dump(),
                        output_preview=preview[:500],
                    )
                )
            except Exception as ex:
                tool_traces.append(
                    ToolTrace(
                        tool=c.tool,
                        status="error",
                        input=c.model_dump(),
                        output_preview=str(ex)[:500],
                    )
                )

    prompt_messages = list(req.messages)
    if ECM_ENABLED and pec_signal is not None:
        prompt_messages.insert(
            0,
            ChatMessage(role="system", content=build_ecm_system_message(pec_signal)),
        )
    if tool_context_lines:
        prompt_messages.append(
            ChatMessage(
                role="system",
                content=(
                    "Tool execution context from this turn:\n" + "\n\n".join(tool_context_lines)
                ),
            )
        )

    profile = load_agent_profile()
    profile_instr = profile.get("instructions") if isinstance(profile.get("instructions"), dict) else {}
    selected_ruleset = find_ruleset(req.ruleset_id)
    selected_system_prompt = find_system_prompt(req.system_prompt_id)
    if profile_instr and str(profile_instr.get("system", "")).strip():
        prompt_messages.insert(0, ChatMessage(role="system", content=str(profile_instr.get("system"))))
    ops = profile_instr.get("operational", []) if isinstance(profile_instr, dict) else []
    safety = profile_instr.get("safety", []) if isinstance(profile_instr, dict) else []
    if isinstance(ops, list) and ops:
        prompt_messages.insert(0, ChatMessage(role="system", content="Operational directives:\n- " + "\n- ".join([str(x) for x in ops])))
    if isinstance(safety, list) and safety:
        prompt_messages.insert(0, ChatMessage(role="system", content="Safety directives:\n- " + "\n- ".join([str(x) for x in safety])))
    if selected_system_prompt and str(selected_system_prompt.get("content", "")).strip():
        prompt_messages.insert(
            0,
            ChatMessage(role="system", content=str(selected_system_prompt.get("content", ""))),
        )
    if selected_ruleset:
        rr = selected_ruleset.get("rules", []) or []
        if rr:
            prompt_messages.insert(
                0,
                ChatMessage(
                    role="system",
                    content="Active ruleset '" + str(selected_ruleset.get("name", selected_ruleset.get("id", "ruleset"))) + "':\n- " + "\n- ".join([str(x) for x in rr]),
                ),
            )

    prompt = build_prompt(
        prompt_messages,
        mode=effective_mode,
        doctrine_level=req.doctrine_level,
        lore_layer=req.lore_layer,
        relationship_context=(
            relationship_context
            + (
                f", pec_persona={pec_signal.persona}, pec_tone={pec_signal.tone}, pec_emotion={pec_signal.emotion}, pec_intensity={pec_signal.intensity}"
                if pec_signal is not None
                else ""
            )
        ),
    )
    now = int(time.time())
    if pec_signal is not None:
        update_memory_from_signal(
            user_messages[-1] if req.messages else "",
            pec_signal,
            req.session_id,
            req.user_id,
            mode_used=effective_mode,
        )

    meta = {
        "mode": effective_mode,
        "requested_mode": req.mode,
        "voice_codec": req.voice_codec,
        "synthetic_grammar": req.synthetic_grammar,
        "lore_layer": req.lore_layer,
        "doctrine_level": req.doctrine_level,
        "relationship_protocol": req.relationship_protocol,
        "session_id": req.session_id,
        "user_id": req.user_id,
        "auto_pec": req.auto_pec,
        "auto_tools": req.auto_tools,
        "tool_trace": [t.model_dump() for t in tool_traces],
        "pec_signal": pec_signal.model_dump() if pec_signal is not None else None,
        "ruleset_id": req.ruleset_id,
        "system_prompt_id": req.system_prompt_id,
    }

    if req.stream:
        created = now

        def event_stream():
            for piece in stream_text_chunks(prompt, req.max_tokens, req.temperature, req.top_p):
                payload = {
                    "id": f"chatcmpl-{uuid.uuid4().hex}",
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": req.model,
                    "choices": [{"index": 0, "delta": {"content": piece}, "finish_reason": None}],
                    "runeforge_meta": meta,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            done_payload = {
                "id": f"chatcmpl-{uuid.uuid4().hex}",
                "object": "chat.completion.chunk",
                "created": created,
                "model": req.model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "runeforge_meta": meta,
            }
            yield f"data: {json.dumps(done_payload)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    text = generate_text(prompt, req.max_tokens, req.temperature, req.top_p)
    text = apply_voice_codec(text, req.voice_codec)
    text = apply_synthetic_grammar(text, req.synthetic_grammar)
    fired_webhooks = fire_webhooks_async(
        payload={
            "session_id": req.session_id,
            "user_id": req.user_id,
            "ruleset_id": req.ruleset_id,
            "system_prompt_id": req.system_prompt_id,
            "mode": effective_mode,
        },
        user_text=(user_messages[-1] if user_messages else ""),
        assistant_text=text,
    )
    meta["fired_webhooks"] = fired_webhooks

    audio = None
    if req.return_audio and text.strip():
        persona = pec_signal.persona if pec_signal is not None else effective_mode
        tone = pec_signal.tone if pec_signal is not None else "calm"
        emotion = pec_signal.emotion if pec_signal is not None else "focused"
        intensity = pec_signal.intensity if pec_signal is not None else "medium"
        auto_tts = tts_params_from_state(persona, tone, emotion, intensity)
        voice = req.speech_voice or str(auto_tts["voice"])
        rate = req.speech_rate or int(auto_tts["rate"])
        try:
            audio = synthesize_speech(text, voice, rate)
        except Exception as ex:
            audio = {"error": str(ex)}

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": now,
        "model": req.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "runeforge_meta": meta,
        "audio": (
            {
                "id": audio.get("id"),
                "voice_id": audio.get("voice_id"),
                "rate": audio.get("rate"),
                "bytes": audio.get("bytes"),
                "download_url": f"/v1/audio/files/{audio.get('id')}",
            }
            if isinstance(audio, dict) and audio.get("id")
            else audio
        ),
    }


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("RUNEFORGE_HOST", "0.0.0.0")
    port = int(os.getenv("RUNEFORGE_PORT", "8008"))
    workers = int(os.getenv("RUNEFORGE_UVICORN_WORKERS", "1"))
    uvicorn.run(
        "runeforge_inference_server:app",
        host=host,
        port=port,
        reload=False,
        workers=workers,
    )
