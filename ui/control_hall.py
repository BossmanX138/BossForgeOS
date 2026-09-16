import atexit
import base64
import json
import os
import re
import subprocess
import sys
import time

from datetime import datetime, timezone
from pathlib import Path

# === Path Resolver for Bundled/Source Modes ===
def get_project_root():
    if getattr(sys, 'frozen', False):
        # PyInstaller bundled mode
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, jsonify, render_template_string, request, send_file


from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.security.bossgate_authorization import BossGateAuthorizationRegistry
from modules.agentforge import api_adapter as agentforge_api
from modules.iconforge import api_adapter as iconforge_api
try:
    from modules.model_gateway import api_adapter as model_gateway_api
except ModuleNotFoundError:
    from core.model_gateway import service as model_gateway_api
from modules.runeforge_voice import service as runeforge_voice_service
from modules.security import api_adapter as security_api
from modules.soundforge import api_adapter as soundforge_api
from modules.ui_runtime import api_adapter as ui_runtime_api
from modules.onboarding import api_adapter as onboarding_api
from modules.ops_runtime import api_adapter as ops_runtime_api
from modules.ops_runtime import agent_state_adapter as agent_state_api

_ASS_HANDOFF_MAX_AGE_SECONDS = 600
_ASS_CONSUMED_LAUNCH_TICKETS: set[str] = set()
from modules.ops_runtime import task_tracker_adapter as task_tracker_api
from modules.collab_runtime import api_adapter as collab_api
from core.state.os_state import build_os_state, diff_os_states
from modules.os_snapshot import snapshot_all


app = Flask(__name__)
bus = RuneBus(resolve_root_from_env())
socketio = None
PIN_OVERLAY_PROCESS = None


def _bossgate_authorization() -> BossGateAuthorizationRegistry:
    return BossGateAuthorizationRegistry(bus.state / "bossgate_human_roles.json")
PIN_OVERLAY_VIEW = ""
PIN_OVERLAY_ALPHA = 0.95
AGENTFORGE_POOL_PATH = PROJECT_ROOT / "state" / "agentforge_custom_pool.json"
AGENT_TASK_TRACKER_PATH = bus.state / "agent_task_tracker.json"
AGENT_ASSIGNMENTS_PATH = PROJECT_ROOT / "AGENT_TASK_ASSIGNMENTS.md"

AGENT_STATUS = {
    "hearth_tender": "Hearth-Tender",
    "archivist": "Archivist",
    "model_gateway": "Model Gateway",
    "security_sentinel": "Security Sentinel",
    "codemage": "CodeMage",
    "runeforge": "Runeforge",
    "devlot": "Devlot",
}

PAGE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>BossForgeOS Control Hall</title>
    <style>
        :root {
            --bg:#0A0A0C;
            --panel:#141417;
            --panel2:#1A1B1F;
            --ink:#e6ddcb;
            --muted:#A9B1C1;
            --line:#5f4a27;
            --accent:#D4A857;
            --ember:#FF7A2F;
            --travel:#4DA6FF;
            --ok:#4CC46A;
            --warn:#FFB84D;
            --bad:#FF4D4D;
        }
        * { box-sizing:border-box; }
        body {
            margin:0;
            font-family:Segoe UI,Tahoma,sans-serif;
            color:var(--ink);
            background:
                radial-gradient(circle at 14% 12%, rgba(255,122,47,0.14), transparent 35%),
                radial-gradient(circle at 86% 88%, rgba(77,166,255,0.10), transparent 30%),
                radial-gradient(circle at 50% 100%, rgba(212,168,87,0.08), transparent 45%),
                var(--bg);
        }
        * {
            scrollbar-width: thin;
            scrollbar-color: rgba(212,168,87,0.55) rgba(16,16,21,0.58);
        }
        *::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        *::-webkit-scrollbar-track {
            background: rgba(16,16,21,0.58);
            border-radius: 10px;
        }
        *::-webkit-scrollbar-thumb {
            background: linear-gradient(180deg, rgba(212,168,87,0.72), rgba(168,128,55,0.70));
            border: 2px solid rgba(16,16,21,0.65);
            border-radius: 10px;
        }
        *::-webkit-scrollbar-thumb:hover {
            background: linear-gradient(180deg, rgba(222,178,96,0.82), rgba(176,136,60,0.78));
        }
        .shell {
            display: grid;
            grid-template-columns: 280px minmax(0, 1fr);
            min-height: 100vh;
        }
        @media (max-width: 1100px) {
            .shell { grid-template-columns: 1fr; }
        }
        .side {
            border-right:1px solid var(--line);
            background:linear-gradient(180deg,#101015,#0D0D11 70%, #0A0A0C);
            padding:14px;
            box-shadow: inset -1px 0 0 rgba(255,122,47,0.10);
            position: sticky;
            top: 0;
            height: 100vh;
            overflow: auto;
            scrollbar-gutter: stable both-edges;
        }
        .side h1 { margin:0 0 8px; color:var(--accent); font-size:18px; }
        .group-label { margin:10px 0 6px; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
        .nav-btn {
            width:100%;
            display:flex;
            align-items:center;
            gap:8px;
            text-align:left;
            margin-bottom:6px;
            border:1px solid rgba(212,168,87,0.35);
            background:linear-gradient(180deg,#19191e,#121218);
            color:var(--ink);
            border-radius:8px;
            padding:8px 10px;
            transition: box-shadow 0.2s ease, border-color 0.2s ease, transform 0.2s ease;
        }
        .nav-btn::before {
            content: '';
            width: 18px;
            height: 18px;
            min-width: 18px;
            display: inline-block;
            border: 1px solid rgba(212,168,87,0.45);
            border-radius: 999px;
            background-image:
                var(--nav-icon, none),
                radial-gradient(circle at 35% 35%, rgba(255,255,255,0.28), rgba(212,168,87,0.22) 55%, rgba(212,168,87,0.08));
            background-size: cover, auto;
            background-position: center, center;
            background-repeat: no-repeat, no-repeat;
            box-shadow: inset 0 0 0 1px rgba(212,168,87,0.22);
            overflow: hidden;
        }
        .nav-btn[data-view="view_cicd"]::before { border-color: rgba(87,209,131,0.85); }
        .nav-btn[data-view="view_sounds"]::before { border-color: rgba(57,255,20,0.85); }
        .nav-btn[data-view="view_iconforge"]::before { border-color: rgba(255,122,47,0.9); }
        .nav-btn[data-view="view_diagnostics"]::before { border-color: rgba(241,113,113,0.88); }
        .nav-btn[data-view="view_security"]::before { border-color: rgba(241,113,113,0.6); }
        .nav-btn[data-view="view_chat"]::before,
        .nav-btn[data-view="view_discovery"]::before { border-color: rgba(107,183,242,0.8); }
        .nav-btn:hover {
            border-color:var(--accent);
            box-shadow: 0 0 0 1px rgba(212,168,87,0.24), 0 0 14px rgba(255,122,47,0.16);
            transform: translateY(-1px);
        }
        .nav-btn.active {
            border-color:var(--accent);
            box-shadow: inset 0 0 0 1px rgba(212,168,87,0.30), 0 0 18px rgba(212,168,87,0.18);
        }
        .wrap {
            width: 100%;
            max-width: 1400px;
            margin: 0 auto;
            padding: 14px 18px 18px;
            display: grid;
            gap: 10px;
            align-content: start;
        }
        .card {
            background:linear-gradient(180deg,var(--panel2),var(--panel));
            border:1px solid var(--line);
            border-radius:12px;
            padding:10px;
            box-shadow: inset 0 0 0 1px rgba(255,122,47,0.06);
        }
        .wrap > .card:first-child {
            position: sticky;
            top: 8px;
            z-index: 5;
            backdrop-filter: blur(6px);
        }
        .row {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            align-items: center;
        }
        .row > * {
            min-height: 32px;
        }
        .row > input,
        .row > select,
        .row > textarea {
            flex: 1 1 220px;
            min-width: 180px;
        }
        .view-panel > .row {
            margin-top: 8px;
            margin-bottom: 8px;
        }
        .view-panel > .row:last-child {
            margin-bottom: 0;
        }
        .view-panel > .muted {
            margin-bottom: 6px;
        }
        .view-panel h2 {
            margin-bottom: 8px;
        }
        .view-panel > pre {
            margin-top: 8px;
        }
        .workspace-grid {
            display: grid;
            grid-template-columns: minmax(260px, 340px) minmax(0, 1fr);
            gap: 10px;
            align-items: start;
        }
        .workspace-pane {
            border: 1px solid #2b2f3a;
            border-radius: 10px;
            padding: 9px;
            min-width: 0;
        }
        .workspace-pane h3 {
            margin: 0 0 6px;
            font-size: 13px;
            color: var(--muted);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .topology-shell {
            margin-top: 8px;
            border: 1px solid #2b2f3a;
            border-radius: 10px;
            background: rgba(12, 14, 20, 0.76);
            padding: 10px;
        }
        .bossgate-presence-layout {
            display: grid;
            gap: 10px;
        }
        .bossgate-presence-stage {
            position: relative;
        }
        .topology-graph {
            width: 100%;
            min-height: 320px;
            border: 1px solid #2b2f3a;
            border-radius: 8px;
            background: radial-gradient(circle at 50% 50%, rgba(77,166,255,0.06), rgba(10,12,18,0.8));
        }
        .bossgate-presence-card {
            border: 1px solid #2b2f3a;
            border-radius: 12px;
            padding: 12px;
            background: linear-gradient(180deg, rgba(15,19,28,0.98), rgba(8,11,17,0.98));
            display: grid;
            gap: 8px;
        }
        .bossgate-presence-title {
            font-size: 16px;
            font-weight: 700;
            color: #edf4ff;
        }
        .bossgate-presence-subtitle {
            font-size: 12px;
            color: var(--muted);
        }
        .bossgate-presence-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: 8px;
        }
        .bossgate-presence-grid-item {
            border: 1px solid #243042;
            border-radius: 10px;
            padding: 8px 10px;
            background: rgba(10,14,20,0.72);
        }
        .bossgate-presence-grid-item strong {
            display: block;
            font-size: 11px;
            color: #8ea0b8;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 4px;
        }
        .bossgate-radial-menu {
            position: absolute;
            transform: translate(-50%, -50%);
            width: 220px;
            height: 220px;
            pointer-events: none;
        }
        .bossgate-radial-center {
            position: absolute;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            width: 96px;
            height: 96px;
            border-radius: 50%;
            border: 1px solid #6ea8ff;
            background: radial-gradient(circle at 40% 35%, rgba(20,39,70,0.98), rgba(8,14,24,0.98));
            color: #edf4ff;
            display: grid;
            place-items: center;
            text-align: center;
            padding: 10px;
            box-shadow: 0 0 26px rgba(77,166,255,0.24);
        }
        .bossgate-radial-action {
            position: absolute;
            width: 74px;
            height: 74px;
            border-radius: 50%;
            border: 1px solid #395374;
            background: radial-gradient(circle at 40% 35%, rgba(23,36,56,0.98), rgba(9,14,22,0.98));
            color: #dbeafe;
            font-size: 11px;
            line-height: 1.2;
            padding: 8px;
            pointer-events: auto;
            cursor: pointer;
        }
        .bossgate-color-green { border-color: #4CC46A; box-shadow: 0 0 18px rgba(76,196,106,0.16); }
        .bossgate-color-blue { border-color: #4DA6FF; box-shadow: 0 0 18px rgba(77,166,255,0.16); }
        .bossgate-color-red { border-color: #FF6262; box-shadow: 0 0 18px rgba(255,98,98,0.16); }
        .bossgate-color-grey { border-color: #94a3b8; box-shadow: 0 0 18px rgba(148,163,184,0.12); }
        .topology-legend {
            margin-top: 6px;
            color: var(--muted);
            font-size: 12px;
        }
        .topology-edge-list {
            margin-top: 8px;
            border-top: 1px solid #2b2f3a;
            padding-top: 8px;
            display: grid;
            gap: 4px;
        }
        .topology-edge-item {
            font-size: 12px;
            color: var(--muted);
        }
        .topology-empty {
            color: var(--muted);
            font-size: 12px;
        }
        .workspace-stack {
            display: grid;
            gap: 6px;
        }
        .workspace-canvas-wrap {
            display: grid;
            grid-template-columns: auto minmax(300px, 1fr);
            gap: 10px;
            align-items: start;
        }
        .workspace-canvas-controls {
            display: grid;
            gap: 6px;
            min-width: 0;
        }
        .iconforge-menubar {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin: 8px 0 10px;
            padding: 6px;
            border: 1px solid #2b2f3a;
            border-radius: 10px;
            background: linear-gradient(180deg, #141117, #0f0d12);
        }
        .iconforge-menu {
            position: relative;
        }
        .iconforge-menu-btn {
            min-height: 28px;
            padding: 4px 10px;
            border-radius: 7px;
            border: 1px solid rgba(212,168,87,0.35);
            background: rgba(20, 19, 24, 0.95);
            color: var(--ink);
            cursor: pointer;
            font-size: 12px;
        }
        .iconforge-menu.open .iconforge-menu-btn {
            border-color: rgba(212,168,87,0.8);
            box-shadow: inset 0 0 0 1px rgba(212,168,87,0.22);
        }
        .iconforge-menu-list {
            display: none;
            position: absolute;
            top: calc(100% + 4px);
            left: 0;
            min-width: 220px;
            z-index: 25;
            border: 1px solid #2b2f3a;
            border-radius: 9px;
            padding: 6px;
            background: #101018;
            box-shadow: 0 10px 20px rgba(0, 0, 0, 0.35);
        }
        .iconforge-menu.open .iconforge-menu-list {
            display: grid;
            gap: 4px;
        }
        .iconforge-menu-list button {
            width: 100%;
            min-height: 28px;
            text-align: left;
            border: 1px solid transparent;
            border-radius: 7px;
            background: rgba(24, 24, 31, 0.95);
            color: var(--ink);
            padding: 5px 8px;
            font-size: 12px;
        }
        .iconforge-menu-list button:hover {
            border-color: rgba(212,168,87,0.55);
            box-shadow: none;
        }
        .menu-shortcut {
            float: right;
            margin-left: 14px;
            color: var(--muted);
            font-size: 11px;
        }
        .iconforge-menu-sep {
            height: 1px;
            margin: 3px 0;
            background: rgba(95, 74, 39, 0.75);
        }
        .iconforge-schematics {
            border: 1px solid #2b2f3a;
            border-radius: 10px;
            padding: 10px;
            margin-bottom: 10px;
            background: linear-gradient(180deg, rgba(17, 14, 20, 0.95), rgba(12, 10, 16, 0.95));
        }
        .iconforge-schematics-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            flex-wrap: wrap;
            margin-bottom: 8px;
        }
        .iconforge-schematics-grid {
            display: grid;
            gap: 8px;
        }
        .iconforge-schematic-section {
            border: 1px solid rgba(95, 74, 39, 0.55);
            border-radius: 10px;
            padding: 8px;
            background: rgba(13, 11, 18, 0.72);
        }
        .iconforge-schematic-section-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin: 0 0 8px;
        }
        .iconforge-schematic-section h3 {
            margin: 0;
            font-size: 12px;
            color: #f2cf86;
            text-transform: uppercase;
            letter-spacing: .05em;
        }
        .iconforge-schematic-toggle {
            min-height: 24px;
            padding: 2px 8px;
            border-radius: 7px;
            border: 1px solid rgba(212,168,87,0.45);
            background: rgba(21, 18, 26, 0.9);
            color: var(--ink);
            font-size: 11px;
            cursor: pointer;
        }
        .iconforge-schematic-toggle:hover {
            border-color: rgba(255,184,77,0.75);
        }
        .iconforge-schematic-section-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 8px;
        }
        .iconforge-schematic-section.collapsed .iconforge-schematic-section-grid {
            display: none;
        }
        .iconforge-schematic-card {
            border: 1px solid rgba(212,168,87,0.35);
            border-radius: 9px;
            background: rgba(18, 16, 23, 0.95);
            padding: 8px;
            display: grid;
            gap: 6px;
            position: relative;
            overflow: visible;
        }
        .iconforge-schematic-card h4 {
            margin: 0;
            font-size: 12px;
            color: #f2cf86;
        }
        .iconforge-schematic-meta {
            font-size: 11px;
            color: var(--muted);
            word-break: break-word;
        }
        .iconforge-schematic-card button {
            min-height: 28px;
        }
        .iconforge-schematic-preview {
            width: 56px;
            height: 56px;
            border: 1px solid rgba(212,168,87,0.45);
            border-radius: 8px;
            background:
                linear-gradient(45deg, rgba(255,255,255,0.08) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.08) 75%),
                linear-gradient(45deg, rgba(255,255,255,0.08) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.08) 75%),
                rgba(14, 14, 20, 0.92);
            background-size: 10px 10px;
            background-position: 0 0, 5px 5px;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
            transition: transform 0.14s ease, box-shadow 0.14s ease, border-color 0.14s ease;
            transform-origin: top left;
        }
        .iconforge-schematic-preview:hover {
            transform: scale(2.5);
            border-color: rgba(255, 184, 77, 0.85);
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.55);
            z-index: 20;
            background-color: rgba(8, 8, 12, 0.98);
        }
        .iconforge-schematic-preview img {
            width: 100%;
            height: 100%;
            object-fit: contain;
            image-rendering: auto;
        }
        .iconforge-schematic-preview-empty {
            font-size: 10px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: .04em;
        }
        .iconforge-schematic-hint {
            font-size: 10px;
            color: var(--muted);
        }
        @media (max-width: 900px) {
            .iconforge-schematic-preview:hover {
                transform: scale(1.6);
            }
        }
        .wizard-layout {
            display: grid;
            grid-template-columns: 220px minmax(0, 1fr);
            gap: 10px;
            align-items: start;
        }
        .wizard-sidebar {
            border: 1px solid #2b2f3a;
            border-radius: 10px;
            padding: 8px;
            background: rgba(12, 12, 16, 0.45);
        }
        .wizard-sidebar h3 {
            margin: 0 0 8px;
            font-size: 12px;
            color: var(--muted);
            text-transform: uppercase;
            letter-spacing: .05em;
        }
        .wizard-checklist {
            display: grid;
            gap: 6px;
        }
        .wizard-check-item {
            width: 100%;
            display: flex;
            align-items: center;
            gap: 8px;
            text-align: left;
            border: 1px solid #2b2f3a;
            border-radius: 8px;
            padding: 6px 8px;
            background: rgba(20, 20, 26, 0.85);
            color: var(--ink);
            cursor: pointer;
        }
        .wizard-check-item .step-dot {
            width: 18px;
            height: 18px;
            border-radius: 999px;
            border: 1px solid rgba(212,168,87,0.45);
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            color: var(--muted);
            background: rgba(18,18,24,0.9);
            flex: 0 0 auto;
        }
        .wizard-check-item.is-active {
            border-color: rgba(212,168,87,0.72);
            box-shadow: inset 0 0 0 1px rgba(212,168,87,0.24);
        }
        .wizard-check-item.is-active .step-dot {
            color: #111;
            background: rgba(212,168,87,0.95);
            border-color: rgba(212,168,87,0.9);
        }
        .wizard-check-item.is-complete .step-dot {
            color: #111;
            background: rgba(175,220,120,0.9);
            border-color: rgba(175,220,120,0.9);
            font-weight: 700;
        }
        .wizard-main {
            min-width: 0;
        }
        h1 { margin:0 0 4px; color:var(--accent); font-size:22px; }
        h2 { margin:0 0 8px; color:var(--accent); font-size:16px; }
        .muted { color:var(--muted); font-size:12px; }
        input, select {
            background:#0E0E13;
            color:var(--ink);
            border:1px solid var(--line);
            border-radius:9px;
            padding:6px 8px;
        }
        textarea {
            background:#0E0E13;
            color:var(--ink);
            border:1px solid var(--line);
            border-radius:9px;
            padding:7px 8px;
            min-height:78px;
            width:100%;
        }
        button {
            background:linear-gradient(180deg,#1d1a12,#14110c);
            color:var(--ink);
            border:1px solid rgba(212,168,87,0.45);
            border-radius:9px;
            padding:6px 10px;
            cursor:pointer;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
            white-space: nowrap;
        }
        button:hover {
            border-color:var(--accent);
            box-shadow: 0 0 0 1px rgba(212,168,87,0.22), 0 0 12px rgba(255,122,47,0.14);
        }
        pre { margin:0; max-height:420px; overflow:auto; white-space:pre-wrap; word-break:break-word; background:#0d1621; border:1px solid var(--line); border-radius:10px; padding:9px; font-size:12px; }
        .agent-item { border:1px solid var(--line); border-radius:9px; padding:8px; margin-bottom:6px; background:#132131; }
        .agent-task-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 8px;
            margin-top: 8px;
        }
        .agent-task-card {
            border: 1px solid #2b2f3a;
            border-radius: 10px;
            padding: 8px;
            background: #0d1621;
        }
        .agent-task-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
            margin-bottom: 6px;
        }
        .agent-task-agent {
            font-weight: 600;
            color: var(--ink);
        }
        .agent-task-text {
            font-size: 12px;
            color: var(--ink);
            margin-bottom: 6px;
            white-space: pre-wrap;
        }
        .agent-task-meta {
            font-size: 11px;
            color: var(--muted);
            margin-bottom: 6px;
        }
        .agent-task-actions {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }
        .agent-task-actions button {
            min-height: 28px;
            padding: 4px 8px;
            font-size: 12px;
        }
        .pill { display:inline-block; margin-left:8px; border-radius:999px; padding:1px 8px; border:1px solid var(--line); font-size:11px; }
        .pill.online { color:var(--ok); border-color:var(--ok); }
        .pill.warning, .pill.stale { color:var(--warn); border-color:var(--warn); }
        .pill.offline, .pill.critical { color:var(--bad); border-color:var(--bad); }
        .view-panel { display:none; }
        .view-panel.active {
            display:block;
            min-height: min(72vh, 980px);
        }
        .panel-heading { display:flex; align-items:center; gap:8px; }
        .panel-icon {
            width:18px;
            height:18px;
            min-width:18px;
            border-radius:4px;
            border:1px solid rgba(212,168,87,0.35);
            object-fit:cover;
            box-shadow: inset 0 0 0 1px rgba(255,255,255,0.08);
        }
        .pin-note { color: var(--muted); font-size: 12px; }
        .busy-indicator {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            margin-top: 8px;
            padding: 4px 10px;
            border: 1px solid var(--line);
            border-radius: 999px;
            background: #0d1621;
            color: var(--muted);
            font-size: 12px;
            opacity: 0;
            transform: translateY(-2px);
            transition: opacity 0.2s ease, transform 0.2s ease;
            pointer-events: none;
        }
        .busy-indicator.active {
            opacity: 1;
            transform: translateY(0);
        }
        .js-error {
            display: none;
            margin-top: 8px;
            padding: 8px 10px;
            border: 1px solid #8a3737;
            border-radius: 8px;
            background: rgba(241, 113, 113, 0.14);
            color: #f17171;
            font-size: 12px;
            white-space: pre-wrap;
        }
        .js-error.active {
            display: block;
        }
        .spinner {
            width: 12px;
            height: 12px;
            border: 2px solid rgba(232, 241, 255, 0.25);
            border-top-color: var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        @media (prefers-reduced-motion: reduce) {
            * {
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }
        }
        .discovery-controls { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin-bottom:10px; }
        .map-shell {
            position: relative;
            border: 1px solid var(--line);
            border-radius: 12px;
            background:
                radial-gradient(circle at 20% 15%, rgba(87, 209, 131, 0.12), transparent 35%),
                radial-gradient(circle at 80% 85%, rgba(242, 201, 107, 0.14), transparent 40%),
                linear-gradient(180deg, #0f1a28, #0b1420);
            min-height: 330px;
            overflow: hidden;
        }
        .map-grid {
            position: absolute;
            inset: 0;
            background-image:
                linear-gradient(to right, rgba(53, 81, 111, 0.35) 1px, transparent 1px),
                linear-gradient(to bottom, rgba(53, 81, 111, 0.35) 1px, transparent 1px);
            background-size: 48px 48px;
            pointer-events: none;
        }
        @media (max-width: 1100px) {
            .side {
                position: static;
                height: auto;
                overflow: visible;
                border-right: 0;
                border-bottom: 1px solid var(--line);
            }
            .nav-btn {
                margin-bottom: 4px;
            }
            .wrap {
                padding: 12px;
            }
            .wrap > .card:first-child {
                position: static;
                top: auto;
            }
            .view-panel.active {
                min-height: 0;
            }
            .workspace-grid {
                grid-template-columns: 1fr;
            }
            .workspace-canvas-wrap {
                grid-template-columns: 1fr;
            }
            .wizard-layout {
                grid-template-columns: 1fr;
            }
            .row > input,
            .row > select,
            .row > textarea {
                min-width: 0;
                flex-basis: 100%;
            }
        }
        .map-watermark {
            position: absolute;
            right: 12px;
            bottom: 8px;
            font-size: 11px;
            color: rgba(157, 177, 201, 0.65);
            letter-spacing: .06em;
            text-transform: uppercase;
            pointer-events: none;
        }
        .map-pin {
            position: absolute;
            transform: translate(-50%, -100%);
            width: 14px;
            height: 14px;
            border-radius: 50% 50% 50% 0;
            transform-origin: 40% 75%;
            transform: translate(-50%, -100%) rotate(-45deg);
            border: 1px solid rgba(255,255,255,0.4);
            box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.25);
            cursor: pointer;
            transition: transform 0.12s ease, box-shadow 0.12s ease;
        }
        .map-pin::after {
            content: '';
            position: absolute;
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: rgba(0,0,0,0.55);
            left: 3px;
            top: 3px;
        }
        .map-pin:hover,
        .map-pin.active {
            box-shadow: 0 0 0 2px rgba(242, 201, 107, 0.5), 0 0 16px rgba(242, 201, 107, 0.25);
            transform: translate(-50%, -100%) rotate(-45deg) scale(1.1);
        }
        .map-pin.assist { background: #f17171; }
        .map-pin.available { background: #57d183; }
        .map-pin.remote { background: #6bb7f2; }
        .discovery-loadout {
            margin-top: 10px;
            border: 1px solid var(--line);
            border-radius: 10px;
            padding: 10px;
            background: #0d1621;
            min-height: 120px;
        }
        .discovery-legend { display:flex; gap:12px; flex-wrap:wrap; margin-top:8px; font-size:12px; color:var(--muted); }
        .legend-dot { display:inline-block; width:10px; height:10px; border-radius:50%; margin-right:6px; }
        .legend-dot.assist { background:#f17171; }
        .legend-dot.available { background:#57d183; }
        .legend-dot.remote { background:#6bb7f2; }
        .snapshot-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
            gap: 10px;
            margin-bottom: 10px;
            position: relative;
        }
        .snapshot-grid.pin-mode {
            border: 1px dashed rgba(212,168,87,0.42);
            border-radius: 10px;
            padding: 6px;
            background: rgba(15, 14, 19, 0.42);
        }
        .gauge-card {
            border: 1px solid rgba(57, 255, 20, 0.38);
            border-radius: 10px;
            padding: 8px;
            background:
                radial-gradient(circle at 10% 0%, rgba(57, 255, 20, 0.2), transparent 38%),
                linear-gradient(155deg, rgba(4, 22, 18, 0.96), rgba(7, 32, 24, 0.94));
            box-shadow:
                inset 0 0 16px rgba(57, 255, 20, 0.13),
                0 0 12px rgba(57, 255, 20, 0.16);
            position: relative;
            overflow: hidden;
        }
        .gauge-card.is-pinned {
            position: absolute;
            z-index: 4;
            width: var(--pinned-width, 210px);
        }
        .snapshot-grid.pin-mode .gauge-card.is-pinned {
            cursor: grab;
            user-select: none;
        }
        .snapshot-grid.pin-mode .gauge-card.is-pinned.dragging {
            cursor: grabbing;
            z-index: 9;
            box-shadow: 0 0 0 2px rgba(242,201,107,0.35), inset 0 0 16px rgba(57,255,20,0.13), 0 10px 20px rgba(0,0,0,0.45);
        }
        .gauge-pin-btn {
            min-height: 22px;
            padding: 1px 7px;
            border-radius: 6px;
            border: 1px solid rgba(87,209,131,0.5);
            background: rgba(8, 28, 18, 0.9);
            color: #9bffb5;
            font-size: 11px;
            cursor: pointer;
            margin-left: 8px;
        }
        .gauge-pin-btn.pinned {
            border-color: rgba(242,201,107,0.7);
            color: #f2cf86;
            background: rgba(38, 30, 12, 0.85);
        }
        .gauge-card::before {
            content: '';
            position: absolute;
            inset: 0;
            background-image: linear-gradient(to right, rgba(57, 255, 20, 0.08) 1px, transparent 1px), linear-gradient(to bottom, rgba(57, 255, 20, 0.05) 1px, transparent 1px);
            background-size: 16px 16px;
            pointer-events: none;
            opacity: 0.45;
        }
        .gauge-head {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 6px;
            position: relative;
            z-index: 1;
            color: #9bff9b;
        }
        .gauge-head .muted {
            font-size: 11px;
            color: #6dffb2;
        }
        .tachometer {
            --pct: 0;
            --tone: #39ff14;
            height: 88px;
            border-radius: 999px 999px 0 0;
            position: relative;
            overflow: hidden;
            background: radial-gradient(circle at 50% 100%, #030f0a 0 48%, transparent 49%);
            border: 1px solid rgba(87, 209, 131, 0.5);
            box-shadow: inset 0 0 26px rgba(57, 255, 20, 0.18);
        }
        .tachometer svg {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
        }
        .tachometer .arc-bg {
            fill: none;
            stroke: rgba(11, 51, 30, 0.9);
            stroke-width: 8;
            stroke-linecap: round;
        }
        .tachometer .arc-fg {
            fill: none;
            stroke: var(--tone);
            stroke-width: 8;
            stroke-linecap: round;
            stroke-dasharray: 100;
            stroke-dashoffset: calc(100 - var(--pct));
            transition: stroke-dashoffset 0.35s ease, stroke 0.35s ease;
            filter: drop-shadow(0 0 6px rgba(57, 255, 20, 0.55));
        }
        .tachometer .arc-rd {
            fill: none;
            stroke: #4da6ff;
            stroke-width: 3;
            stroke-linecap: round;
            stroke-dasharray: 100;
            stroke-dashoffset: calc(100 - var(--rdpct, 0));
            opacity: 0.95;
            transition: stroke-dashoffset 0.35s ease;
        }
        .tachometer .arc-wr {
            fill: none;
            stroke: #ffb84d;
            stroke-width: 2;
            stroke-linecap: round;
            stroke-dasharray: 100;
            stroke-dashoffset: calc(100 - var(--wrpct, 0));
            opacity: 0.95;
            transition: stroke-dashoffset 0.35s ease;
        }
        .tachometer .halo {
            position: absolute;
            inset: -9px;
            border-radius: 999px 999px 0 0;
            border: 1px solid rgba(57, 255, 20, 0.18);
            pointer-events: none;
            filter: blur(1px);
            opacity: 0.25;
            animation: haloPulseLow 3.2s ease-in-out infinite;
        }
        .tachometer.pulse-mid .halo {
            opacity: 0.42;
            animation: haloPulseMid 2.1s ease-in-out infinite;
        }
        .tachometer.pulse-high .halo {
            opacity: 0.6;
            border-color: rgba(57, 255, 20, 0.42);
            animation: haloPulseHigh 1.3s ease-in-out infinite;
        }
        .tachometer .ticks {
            position: absolute;
            inset: 0;
            border-radius: inherit;
            background: repeating-conic-gradient(
                from 180deg,
                rgba(151, 255, 176, 0.45) 0deg,
                rgba(151, 255, 176, 0.45) 1deg,
                transparent 1deg,
                transparent 8deg
            );
            mask: radial-gradient(circle at 50% 100%, transparent 0 45%, #000 46% 100%);
            pointer-events: none;
            opacity: 0.6;
        }
        .tachometer::before {
            content: '';
            position: absolute;
            inset: 0;
            background: repeating-linear-gradient(0deg, rgba(57, 255, 20, 0.09) 0px, rgba(57, 255, 20, 0.09) 1px, transparent 3px, transparent 6px);
            animation: holoScan 2.6s linear infinite;
            pointer-events: none;
        }
        .tachometer::after {
            content: '';
            position: absolute;
            left: 50%;
            bottom: 0;
            width: 3px;
            height: 44px;
            border-radius: 2px;
            background: #7dff8b;
            transform-origin: 50% 100%;
            transform: translateX(-50%) rotate(calc((var(--pct) - 50) * 1.8deg));
            box-shadow: 0 0 14px rgba(125, 255, 139, 0.78);
            transition: transform 0.35s ease;
        }
        .tachometer.sweep::after {
            animation: needleSweep 1.05s cubic-bezier(0.2, 0.8, 0.15, 1) 1;
        }
        @keyframes holoScan {
            0% { transform: translateY(-100%); opacity: 0.2; }
            45% { opacity: 0.5; }
            100% { transform: translateY(100%); opacity: 0.15; }
        }
        @keyframes needleSweep {
            0% {
                transform: translateX(-50%) rotate(-90deg);
                box-shadow: 0 0 4px rgba(125, 255, 139, 0.4);
            }
            65% {
                transform: translateX(-50%) rotate(92deg);
                box-shadow: 0 0 16px rgba(125, 255, 139, 0.95);
            }
            100% {
                transform: translateX(-50%) rotate(calc((var(--pct) - 50) * 1.8deg));
                box-shadow: 0 0 14px rgba(125, 255, 139, 0.78);
            }
        }
        @keyframes haloPulseLow {
            0% { box-shadow: 0 0 8px rgba(57, 255, 20, 0.12); }
            50% { box-shadow: 0 0 18px rgba(57, 255, 20, 0.22); }
            100% { box-shadow: 0 0 8px rgba(57, 255, 20, 0.12); }
        }
        @keyframes haloPulseMid {
            0% { box-shadow: 0 0 10px rgba(57, 255, 20, 0.2); }
            50% { box-shadow: 0 0 24px rgba(57, 255, 20, 0.38); }
            100% { box-shadow: 0 0 10px rgba(57, 255, 20, 0.2); }
        }
        @keyframes haloPulseHigh {
            0% { box-shadow: 0 0 12px rgba(57, 255, 20, 0.28); }
            50% { box-shadow: 0 0 28px rgba(57, 255, 20, 0.55); }
            100% { box-shadow: 0 0 12px rgba(57, 255, 20, 0.28); }
        }
        .gauge-foot {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #6dffb2;
            margin-top: 4px;
            position: relative;
            z-index: 1;
        }
        .snapshot-warning-list {
            margin: 0 0 10px;
            padding: 0;
            list-style: none;
            display: grid;
            gap: 4px;
        }
        .snapshot-warning-item {
            border: 1px solid rgba(57, 255, 20, 0.48);
        .gauge-legend {
            margin-top: 4px;
            display: flex;
            gap: 8px;
            align-items: center;
            flex-wrap: wrap;
            font-size: 10px;
            color: #9bb0c9;
            position: relative;
            z-index: 1;
        }
        .gauge-legend-item {
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .gauge-legend-line {
            display: inline-block;
            width: 14px;
            border-radius: 2px;
        }
        .gauge-legend-line.usage {
            height: 4px;
            background: #39ff14;
        }
        .gauge-legend-line.read {
            height: 3px;
            background: #4da6ff;
        }
        .gauge-legend-line.write {
            height: 2px;
            background: #ffb84d;
        }
            background: rgba(57, 255, 20, 0.12);
            color: #8bff9d;
            border-radius: 8px;
            padding: 5px 8px;
            font-size: 12px;
            box-shadow: inset 0 0 8px rgba(57, 255, 20, 0.16);
        }
        .snapshot-warning-item.good {
            border-color: rgba(87, 209, 131, 0.55);
            background: rgba(87, 209, 131, 0.14);
            color: #9bffb5;
        }
        .snapshot-warning-item.bad {
            border-color: #8a3737;
            background: rgba(241, 113, 113, 0.14);
            color: #f17171;
        }
    </style>
</head>
<body>
    <div class="shell">
        <aside class="side">
            <h1 id="shell_title">BossForgeOS</h1>
            <div id="shell_subtitle" class="muted">Control Hall</div>
            <div class="group-label">Operations</div>
            <button class="nav-btn" data-view="view_status" onclick="switchView('view_status')">Agent Status</button>
            <button class="nav-btn" data-view="view_delegation" onclick="switchView('view_delegation')">Delegation Flow</button>
            <button class="nav-btn" data-view="view_snapshot" onclick="switchView('view_snapshot')">OS Snapshot</button>
            <button class="nav-btn" data-view="view_os_state" onclick="switchView('view_os_state')">OS State</button>
            <button class="nav-btn" data-view="view_commands" onclick="switchView('view_commands')">Quick Commands</button>
            <button class="nav-btn" data-view="view_manual" onclick="switchView('view_manual')">Manual Command</button>
            <button class="nav-btn" data-view="view_seal" onclick="switchView('view_seal')">Seal Queue</button>
            <button class="nav-btn" data-view="view_events" onclick="switchView('view_events')">Recent Events</button>
            <button class="nav-btn" data-view="view_bus" onclick="switchView('view_bus')">Bus Inspector</button>
            <button class="nav-btn" data-view="view_cicd" onclick="switchView('view_cicd')" style="color:#57d183; font-weight:bold;">CI/CD</button>
            <button class="nav-btn" data-view="view_onboarding" onclick="switchView('view_onboarding')" style="color:#f2c96b; font-weight:bold;">Onboarding Wizard</button>
            <button class="nav-btn" data-view="view_scheduler" onclick="switchView('view_scheduler')" style="color:#f2c96b; font-weight:bold;">Scheduler</button>
            <div class="group-label">Assistants</div>
            <button class="nav-btn" data-view="view_chat" onclick="switchView('view_chat')">Model Chat</button>
            <button class="nav-btn" data-view="view_maker" onclick="switchView('view_maker')">AgentForge</button>
            <button class="nav-btn" data-view="view_bossgate_map" data-bossgate-panel="bossgate_map" onclick="switchView('view_bossgate_map')">BossGate Map</button>
            <button class="nav-btn" data-view="view_bossgate_access" data-bossgate-panel="operator" onclick="switchView('view_bossgate_access')">BossGate Access</button>
            <button class="nav-btn" data-view="view_bossgate_commerce" data-bossgate-panel="commerce" onclick="switchView('view_bossgate_commerce')">BossGate Commerce</button>
            <button class="nav-btn" data-view="view_bossgate_support" data-bossgate-panel="support" onclick="switchView('view_bossgate_support')">BossGate Support</button>
            <button class="nav-btn" data-view="view_iconforge" onclick="switchView('view_iconforge')" style="color:#ffb27d; font-weight:bold;">IconForge Studio</button>
            <button class="nav-btn" data-view="view_discovery" data-bossgate-panel="discovery" onclick="switchView('view_discovery')">Discovery Map</button>
            <button class="nav-btn" data-view="view_security" onclick="switchView('view_security')">Security</button>
            <button class="nav-btn" data-view="view_sounds" onclick="switchView('view_sounds')" style="color:#39ff14; font-weight:bold;">Sounds</button>
            <div class="group-label">Diagnostics</div>
            <button class="nav-btn" data-view="view_diagnostics" onclick="switchView('view_diagnostics')" style="color:#f17171; font-weight:bold;">Diagnostics</button>
        </aside>

        <main class="wrap">
            <section class="card">
                <h1 id="hall_title">BossForgeOS Control Hall</h1>
                <div id="hall_subtitle" class="muted">Panels open in center. Pin any active panel to always-on-top desktop overlay.</div>
                <div id="hall_pin_row" class="row" style="margin-top:8px;">
                    <button id="pin_toggle" onclick="togglePinCurrentView()">Pin Current View</button>
                    <button onclick="clearPinnedView()">Unpin</button>
                    <span id="pin_note" class="pin-note">No desktop pin active</span>
                </div>
                <button id="anvil_launch_btn" class="anvil-btn" onclick="launchAnvilShuttle()">Launch Anvil Secured Shuttle</button>
                <div id="anvil_status" class="muted" style="margin-top:8px;"></div>
                <script>
                async function launchAnvilShuttle() {
                    const statusEl = document.getElementById('anvil_status');
                    if (statusEl) statusEl.textContent = 'Launching Anvil Secured Shuttle...';
                    try {
                        const res = await fetch('/api/launch_anvil_shuttle', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                        const data = await res.json();
                        if (statusEl) statusEl.textContent = data.ok ? 'Anvil Secured Shuttle launched.' : ('Launch failed: ' + (data.message || 'unknown error'));
                    } catch (e) {
                        if (statusEl) statusEl.textContent = 'Launch error: ' + e;
                    }
                }
                </script>
                <div id="toast" class="muted" style="margin-top:8px;"></div>
                <div id="busy_indicator" class="busy-indicator" aria-live="polite">
                    <span class="spinner" aria-hidden="true"></span>
                    <span id="busy_text">Loading...</span>
                </div>
                <div id="js_error" class="js-error" aria-live="assertive"></div>
            </section>

            <section id="view_status" class="card view-panel">
                <h2>Agent Status</h2>
                <div id="agents" class="muted">Loading...</div>
                <div class="row" style="margin-top:10px;">
                    <h2 style="margin:0;">Agent Task Tracker</h2>
                    <button onclick="refreshAgentTaskTracker()">Refresh Task Tracker</button>
                </div>
                <div class="muted">Live task ownership and execution state for assigned agent TODOs.</div>
                <div id="agent_task_tracker" class="agent-task-grid"></div>
            </section>
            <section id="view_delegation" class="card view-panel">
                <h2>Delegation Flow</h2>
                <div class="muted">Archivist -> Runeforge review -> subordinate agents -> in-progress/completed.</div>
                <div class="row" style="margin-top:8px;">
                    <button onclick="refreshDelegationFlowPanel()">Refresh Delegation Flow</button>
                </div>
                <div id="delegation_flow_summary" class="row" style="margin-top:8px;"></div>
                <div id="delegation_flow_chips" style="margin-top:8px;"></div>
                <div id="delegation_flow_timeline" class="row" style="margin-top:8px;"></div>
                <pre id="delegation_flow_raw">Loading...</pre>
            </section>
            <section id="view_snapshot" class="card view-panel">
                <h2>OS Snapshot</h2>
                <div class="row" style="margin-bottom:8px;">
                    <button id="snapshot_pin_mode_btn" onclick="toggleSnapshotGaugePinMode()">Gauge Pin Mode: Off</button>
                    <button onclick="resetSnapshotGaugePins()">Reset Gauge Pins</button>
                    <span id="snapshot_pin_mode_note" class="muted">Pin gauges to make a movable loadout.</span>
                </div>
                <div id="runeforge_voice_status" class="agent-item" style="margin-bottom:10px;">
                    <strong>Runeforge Voice Safety</strong>
                    <div class="muted">Loading approval and execution status...</div>
                </div>
                <div id="snapshot_dashboard" class="snapshot-grid"></div>
                <ul id="snapshot_warnings" class="snapshot-warning-list"></ul>
                <pre id="snapshot">Loading...</pre>
            </section>

            <section id="view_os_state" class="card view-panel">
                <h2>OS State</h2>
                <div class="muted">Canonical state schema feed and diff stream for time-travel debugging prep.</div>
                <div class="row" style="margin-top:8px;">
                    <button onclick="refreshOsStatePanel()">Refresh OS State</button>
                </div>
                <pre id="os_state">Loading...</pre>
                <h2 style="margin-top:10px;">OS State Diff</h2>
                <pre id="os_state_diff">No diff yet.</pre>
            </section>

            <section id="view_commands" class="card view-panel">
                <h2>Quick Commands</h2>
                <div class="row">
                    <button onclick="sendCmd('hearth_tender','status_ping',{})">Daemon Ping</button>
                    <button onclick="sendCmd('archivist','snapshot_state',{})">Snapshot State</button>
                    <button onclick="sendCmd('model_gateway','status_ping',{})">Model Gateway Ping</button>
                    <button onclick="sendCmd('security_sentinel','scan_workspace',{})">Security Scan</button>
                </div>
            </section>

            <section id="view_manual" class="card view-panel">
                <h2>Manual Command</h2>
                <div class="row">
                    <select id="target"></select>
                    <input id="command" value="status_ping" placeholder="command" />
                    <input id="args" value="{}" placeholder="args JSON" style="min-width:260px;" />
                    <button onclick="sendManual()">Dispatch</button>
                    <button onclick="refresh()">Refresh</button>
                </div>
            </section>

            <section id="view_seal" class="card view-panel"><h2>Seal Queue</h2><pre id="seal">Loading...</pre></section>
            <section id="view_events" class="card view-panel"><h2>Recent Events</h2><pre id="events">Loading...</pre></section>

            <section id="view_bus" class="card view-panel">
                <h2>Bus Inspector</h2>
                <div class="muted">Live view of latest commands, events, and state snapshots on the Rune Bus.</div>
                <div class="row" style="margin-top:8px;">
                    <input id="bus_limit" type="number" min="10" max="300" value="80" style="width:120px;" />
                    <select id="bus_kind" style="min-width:160px;">
                        <option value="events,commands,state">all kinds</option>
                        <option value="events">events only</option>
                        <option value="commands">commands only</option>
                        <option value="state">state only</option>
                    </select>
                    <input id="bus_query" placeholder="filter text (source/target/event/file)" style="min-width:280px;" />
                    <label class="muted"><input type="checkbox" id="bus_live" /> Live</label>
                    <button onclick="refreshBusInspector()">Refresh Bus Inspector</button>
                </div>
                <pre id="bus_inspector">Loading...</pre>
            </section>

            <section id="view_discovery" class="card view-panel">
                <h2>Discovery Map</h2>
                <div class="muted">Network map-style targeting with pin loadouts for discovered agents and nodes.</div>
                <div class="discovery-controls">
                    <label class="muted"><input type="checkbox" id="discovery_assistance_only" /> Assistance only</label>
                    <button onclick="refreshDiscoveryMap()">Refresh Discovery</button>
                    <button onclick="refreshOwnedLocations()">Refresh My Agent Locations</button>
                    <span id="discovery_summary" class="muted"></span>
                </div>
                <div id="discovery_map" class="map-shell">
                    <div class="map-grid"></div>
                    <div class="map-watermark">BossGate Tactical Grid</div>
                </div>
                <div class="discovery-legend">
                    <span><span class="legend-dot assist"></span>Assistance Requested</span>
                    <span><span class="legend-dot available"></span>Travel-Eligible</span>
                    <span><span class="legend-dot remote"></span>Remote or Restricted</span>
                </div>
                <div id="discovery_loadout" class="discovery-loadout muted">Select a pin to inspect its loadout.</div>
                <pre id="discovery_raw">No discovery data loaded.</pre>
            </section>

            <section id="view_bossgate_map" class="card view-panel">
                <h2>BossGate Map</h2>
                <div class="muted">Live gate beacon topology showing gates, travelable destinations, and agent locations.</div>
                <div class="row">
                    <button onclick="refreshBossGateMap(true)">Refresh BossGate Map</button>
                    <span id="bossgate_map_summary" class="muted"></span>
                </div>
                <div id="bossgate_topology" class="topology-shell">
                    <div class="topology-empty">No map topology loaded yet.</div>
                </div>
                <pre id="bossgate_map_raw">No BossGate map loaded.</pre>
            </section>

            <section id="view_bossgate_access" class="card view-panel">
                <h2>BossGate Access</h2>
                <div class="muted">Human-role permissions control which BossGate mechanisms are available.</div>
                <div class="row">
                    <input id="bossgate_current_user" value="bossforge-owner" placeholder="current human user" />
                    <button onclick="refreshBossGateAccess()">Load Access</button>
                </div>
                <pre id="bossgate_access_summary">Load a user to inspect roles and permissions.</pre>
                <div data-bossgate-permission="bossgate.package">
                    <h3>Operator Package</h3>
                    <div class="row">
                        <input id="bossgate_package_agent_name" placeholder="agent name" />
                        <input id="bossgate_package_target" placeholder="target system id" />
                        <button onclick="dispatchBossGateOperator('bossgate_package_agent')">Package Agent</button>
                    </div>
                </div>
                <div data-bossgate-permission="bossgate.transfer">
                    <h3>Operator Transfer</h3>
                    <div class="row">
                        <input id="bossgate_transfer_file" placeholder="package file" />
                        <input id="bossgate_transfer_destination" placeholder="destination URL" />
                        <button onclick="dispatchBossGateOperator('bossgate_transfer_agent')">Transfer Agent</button>
                    </div>
                </div>
                <div data-bossgate-permission="bossgate.install">
                    <h3>Operator Install</h3>
                    <div class="row">
                        <input id="bossgate_install_file" placeholder="package file" />
                        <button onclick="dispatchBossGateOperator('bossgate_install_agent')">Install Agent</button>
                    </div>
                </div>
                <div data-bossgate-panel="security_admin">
                    <h3>Security Administration</h3>
                    <div class="row">
                        <input id="bossgate_assign_user" placeholder="human user id" />
                        <input id="bossgate_assign_roles" placeholder="roles, comma separated" />
                        <button onclick="assignBossGateRoles()">Assign Roles</button>
                    </div>
                    <div class="row">
                        <input id="bossgate_custom_role" placeholder="custom role name" />
                        <input id="bossgate_custom_permissions" placeholder="permissions, comma separated" />
                        <button onclick="saveBossGateCustomRole()">Save Custom Role</button>
                    </div>
                </div>
            </section>

            <section id="view_bossgate_commerce" class="card view-panel">
                <h2>BossGate Commerce</h2>
                <div class="muted">Commerce responsibility workspace. License issue, validation, and usage report commands are permission-mapped and remain pending under BG-017 through BG-021.</div>
                <pre id="bossgate_commerce_summary">Load BossGate Access to inspect commerce permissions.</pre>
            </section>

            <section id="view_bossgate_support" class="card view-panel">
                <h2>BossGate Support</h2>
                <div class="muted">Support responsibility workspace. Remote-debug open and close controls are permission-mapped and remain pending under BG-022 through BG-025.</div>
                <pre id="bossgate_support_summary">Load BossGate Access to inspect support permissions.</pre>
            </section>

            <section id="view_chat" class="card view-panel">
                <h2>Model Chat</h2>
                <div class="row"><select id="chat_endpoint"></select><input id="chat_system" value="You are BossForgeOS assistant." placeholder="system prompt" /></div>
                <pre id="chat_log">No messages yet.</pre>
                <textarea id="chat_prompt" placeholder="Message model endpoint..."></textarea>
                <div class="row"><button onclick="sendChat()">Send</button></div>
            </section>

            <section id="view_diagnostics" class="card view-panel">
                <h2 style="color:#f17171;">Diagnostics</h2>
                <div class="muted">Agent health, recent errors, and TODOs across the system.</div>
                <pre id="diagnostics_output">Open this panel to load diagnostics.</pre>
                <div class="row"><button onclick="refreshDiagnostics()">Refresh Diagnostics</button></div>
            </section>

            <section id="view_sounds" class="card view-panel">
                <h2 style="color:#39ff14;">Sounds</h2>
                <div class="muted">Sound scheme and SoundForge bundle tools.</div>
                <div class="workspace-grid" style="margin-top:8px;">
                    <div class="workspace-pane workspace-stack">
                        <h3>SoundForge Actions</h3>
                        <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="saveSoundScheme()">Save Scheme</button>
                        <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="loadSoundScheme()">Load Scheme</button>
                        <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="createNewScheme()">Create New Scheme</button>
                        <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="exportSoundforgeBundle()">Export Bundle</button>
                        <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="showImportBundleDialog()">Import Bundle</button>
                        <div id="sound_scheme_status" class="muted" style="margin-top:2px;"></div>
                        <div id="soundforge_schemes_list" class="muted"></div>
                    </div>
                    <div class="workspace-pane workspace-stack">
                        <h3>Sound Scheme State</h3>
                        <pre id="sound_events">Open this panel to load sound status.</pre>
                    </div>
                </div>
                <input type="file" id="sound_scheme_file" style="display:none;" accept=".json,.soundstage" onchange="handleSchemeFile(event)" />
                <input type="file" id="soundforge_bundle_file" style="display:none;" accept=".B4Gsoundforge,.B4Gsoundstage,application/zip" onchange="handleImportBundle(event)" />
            </section>

            <section id="view_maker" class="card view-panel">
                <h2>AgentForge</h2>
                <div class="row">
                    <button onclick="switchAgentForgeMode('wizard')" id="maker_mode_wizard_btn">Wizard Mode</button>
                    <button onclick="switchAgentForgeMode('advanced')" id="maker_mode_advanced_btn">Advanced Mode</button>
                    <button onclick="refreshAgentMaker()">Refresh Agents</button>
                </div>
                <pre id="maker_agents">Loading...</pre>

                <div id="maker_wizard_mode" style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0;">
                    <div class="muted" style="margin-bottom:8px;">Wizard flow: answer each step, review, then finalize.</div>
                    <div id="wizard_step_label" class="muted" style="margin-bottom:8px;">Step 1 of 4: Identity</div>
                    <div class="wizard-layout">
                        <aside class="wizard-sidebar">
                            <h3>Checklist</h3>
                            <div class="wizard-checklist">
                                <button class="wizard-check-item" data-check-step="1" onclick="setWizardStep(1)"><span class="step-dot">1</span><span>Identity</span></button>
                                <button class="wizard-check-item" data-check-step="2" onclick="setWizardStep(2)"><span class="step-dot">2</span><span>Profile</span></button>
                                <button class="wizard-check-item" data-check-step="3" onclick="setWizardStep(3)"><span class="step-dot">3</span><span>Capabilities</span></button>
                                <button class="wizard-check-item" data-check-step="4" onclick="setWizardStep(4)"><span class="step-dot">4</span><span>Review</span></button>
                            </div>
                        </aside>
                        <div class="wizard-main">

                    <div class="wizard-step" data-wizard-step="1">
                        <div class="row">
                            <input id="wizard_name" placeholder="agent name" />
                            <select id="wizard_endpoint"></select>
                            <input id="wizard_role_focus" placeholder="what should this agent do?" />
                        </div>
                    </div>

                    <div class="wizard-step" data-wizard-step="2" style="display:none;">
                        <div class="row">
                            <select id="wizard_scope">
                                <option value="host">Local Host</option>
                                <option value="lan">LAN</option>
                                <option value="remote">Remote/Customer</option>
                            </select>
                            <select id="wizard_behavior">
                                <option value="directive_local">Directive Local Specialist</option>
                                <option value="proactive_remote">Proactive Remote Fixer</option>
                                <option value="security_guard">Security Watcher</option>
                                <option value="qa_tester">QA/Test Specialist</option>
                            </select>
                            <select id="wizard_power">
                                <option value="normalized">Normalized</option>
                                <option value="skilled" selected>Skilled</option>
                                <option value="prime">Prime</option>
                            </select>
                        </div>
                        <div class="row">
                            <select id="wizard_personality">
                                <option value="balanced" selected>personality: balanced</option>
                                <option value="decisive">personality: decisive</option>
                                <option value="cautious">personality: cautious</option>
                                <option value="creative">personality: creative</option>
                                <option value="analytical">personality: analytical</option>
                                <option value="introvert_local">personality: i don't like crowded places</option>
                            </select>
                            <input id="wizard_personality_notes" placeholder="personality notes (optional)" />
                            <input id="wizard_personality_interests" placeholder="interests e.g. ui, art, animation (comma-separated)" />
                        </div>
                    </div>

                    <div class="wizard-step" data-wizard-step="3" style="display:none;">
                        <div class="row">
                            <select id="wizard_behavior_patterns" multiple size="4" style="min-width:260px;">
                                <option value="authority_like">authority_like</option>
                                <option value="controller_like">controller_like</option>
                                <option value="worker_like">worker_like</option>
                                <option value="security_like">security_like</option>
                                <option value="tester_like">tester_like</option>
                                <option value="ranger_like">ranger_like</option>
                                <option value="ranger_local">ranger_local</option>
                            </select>
                        </div>
                        <div class="row">
                            <select id="wizard_skill_list" multiple size="4" style="min-width:260px;">
                                <option value="command">command</option>
                                <option value="bossgate_travel_control">bossgate_travel_control</option>
                                <option value="runtime_observation">runtime_observation</option>
                                <option value="task_queue_management">task_queue_management</option>
                                <option value="web_search">web_search</option>
                                <option value="policy_planning">policy_planning</option>
                                <option value="memory_sync">memory_sync</option>
                                <option value="incident_triage">incident_triage</option>
                                <option value="code_review">code_review</option>
                                <option value="ui_design">ui_design</option>
                                <option value="art_direction">art_direction</option>
                                <option value="documentation_crafting">documentation_crafting</option>
                                <option value="test_orchestration">test_orchestration</option>
                                <option value="security_audit">security_audit</option>
                                <option value="performance_tuning">performance_tuning</option>
                                <option value="data_analysis">data_analysis</option>
                                <option value="workflow_automation">workflow_automation</option>
                                <option value="customer_support">customer_support</option>
                                <option value="integration_mapping">integration_mapping</option>
                                <option value="api_composition">api_composition</option>
                            </select>
                            <select id="wizard_state_machine_template" style="min-width:260px;" onchange="syncWizardStateMachinePreview()">
                                <option value="none" selected>state machine: none</option>
                                <option value="basic_lifecycle">state machine: basic lifecycle</option>
                                <option value="delegation_flow">state machine: delegation flow</option>
                                <option value="incident_response">state machine: incident response</option>
                            </select>
                            <select id="wizard_sigil_list" multiple size="4" style="min-width:260px;">
                                <option value="sigil_transporter">sigil_transporter</option>
                                <option value="prime_overwatch">prime_overwatch</option>
                                <option value="sigil_bind">sigil_bind</option>
                                <option value="sigil_trace">sigil_trace</option>
                                <option value="sigil_harmony">sigil_harmony</option>
                                <option value="prime_foresight">prime_foresight</option>
                                <option value="prime_bastion">prime_bastion</option>
                                <option value="sigil_palette">sigil_palette</option>
                                <option value="sigil_resonance">sigil_resonance</option>
                                <option value="sigil_flux">sigil_flux</option>
                                <option value="sigil_anchor">sigil_anchor</option>
                                <option value="sigil_lens">sigil_lens</option>
                                <option value="sigil_weave">sigil_weave</option>
                                <option value="sigil_echo">sigil_echo</option>
                                <option value="sigil_guard">sigil_guard</option>
                                <option value="sigil_spark">sigil_spark</option>
                                <option value="sigil_patch">sigil_patch</option>
                                <option value="sigil_scribe">sigil_scribe</option>
                                <option value="sigil_orbit">sigil_orbit</option>
                                <option value="sigil_shield">sigil_shield</option>
                            </select>
                        </div>
                        <div id="wizard_state_machine_hint" class="muted" style="margin-top:6px;">No state machine selected. Agent runtime can remain stateless.</div>
                        <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0;">
                            <div class="muted" style="margin-bottom:8px;">Custom Icon (Wizard)</div>
                            <div class="row">
                                <select id="wizard_icon_mode" onchange="toggleWizardIconSource()">
                                    <option value="none" selected>icon: default</option>
                                    <option value="upload">icon: upload file</option>
                                    <option value="iconforge">icon: create in IconForge</option>
                                </select>
                                <input id="wizard_icon_path" placeholder="custom icon path (.ico)" readonly />
                                <button onclick="clearWizardIconSelection()">Clear Icon</button>
                            </div>
                            <div id="wizard_icon_upload_row" class="row" style="display:none; margin-top:6px;">
                                <button onclick="triggerWizardIconUpload()">Upload Icon/Image</button>
                                <span id="wizard_icon_upload_name" class="muted">No file selected</span>
                                <input id="wizard_icon_upload_file" type="file" style="display:none;" accept=".png" onchange="handleWizardIconUpload(event)" />
                            </div>
                            <div id="wizard_iconforge_row" class="row" style="display:none; margin-top:6px;">
                                <input id="wizard_icon_label" maxlength="3" value="AG" placeholder="label (max 3)" />
                                <input id="wizard_icon_bg" value="#1d3557" placeholder="background color" />
                                <input id="wizard_icon_fg" value="#f1faee" placeholder="foreground color" />
                                <button onclick="createWizardIconForge()">Create In IconForge</button>
                                <button onclick="openIconForgeFromAgentForge('wizard')">Open IconForge Session</button>
                            </div>
                            <div id="wizard_icon_status" class="muted" style="margin-top:6px;">Using default icon.</div>
                        </div>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;">
                            <input id="wizard_encrypt_profile" type="checkbox" checked /> Hide proprietary profile details
                        </label>
                    </div>

                    <div class="wizard-step" data-wizard-step="4" style="display:none;">
                        <div class="muted" style="margin-bottom:8px;">Review your choices before creating.</div>
                        <pre id="wizard_review">No wizard summary yet.</pre>
                    </div>

                    <div class="row" style="margin-top:10px;">
                        <button id="wizard_back_btn" onclick="wizardPrevStep()">Back</button>
                        <button id="wizard_next_btn" onclick="wizardNextStep()">Next</button>
                        <button id="wizard_review_btn" onclick="wizardOpenReview()">Review</button>
                        <button onclick="buildWizardDraft()">Build Draft In Advanced</button>
                        <button id="wizard_create_btn" onclick="createWizardAgent()">Create From Wizard</button>
                    </div>
                        </div>
                    </div>
                </div>

                <div id="maker_advanced_mode" style="display:none; border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0;">
                    <div class="muted" style="margin-bottom:8px;">Advanced role/policy-aware mode. Invalid combinations are prevented automatically.</div>
                    <div class="row">
                        <input id="maker_name" placeholder="agent name" />
                        <select id="maker_endpoint"></select>
                        <input id="maker_system" value="You are a helpful specialist agent." placeholder="system prompt" />
                    </div>
                    <div class="row">
                        <select id="maker_personality" onchange="syncAdvancedPolicyAwareness()">
                            <option value="balanced" selected>personality: balanced</option>
                            <option value="decisive">personality: decisive</option>
                            <option value="cautious">personality: cautious</option>
                            <option value="creative">personality: creative</option>
                            <option value="analytical">personality: analytical</option>
                            <option value="introvert_local">personality: i don't like crowded places</option>
                        </select>
                        <input id="maker_personality_notes" placeholder="personality notes (optional wrapper directives)" onchange="syncAdvancedPolicyAwareness()" />
                        <input id="maker_personality_interests" placeholder="interests e.g. ui, art, design systems (comma-separated)" onchange="syncAdvancedPolicyAwareness()" />
                    </div>
                    <div class="row">
                        <select id="maker_behavior_patterns" multiple size="4" style="min-width:260px;" onchange="syncAdvancedPolicyAwareness()">
                            <option value="authority_like">authority_like</option>
                            <option value="controller_like">controller_like</option>
                            <option value="worker_like">worker_like</option>
                            <option value="security_like">security_like</option>
                            <option value="tester_like">tester_like</option>
                            <option value="ranger_like">ranger_like</option>
                            <option value="ranger_local">ranger_local</option>
                        </select>
                    </div>
                    <div class="row">
                        <select id="maker_agent_class" onchange="syncAdvancedPolicyAwareness()">
                            <option value="normalized">normalized</option>
                            <option value="skilled" selected>skilled</option>
                            <option value="prime">prime</option>
                        </select>
                        <select id="maker_agent_type" onchange="syncAdvancedPolicyAwareness()">
                            <option value="controller" selected>controller</option>
                            <option value="ranger">ranger</option>
                            <option value="authority">authority</option>
                            <option value="worker">worker</option>
                            <option value="security">security</option>
                            <option value="tester">tester</option>
                        </select>
                        <select id="maker_rank" onchange="syncAdvancedPolicyAwareness()">
                            <option value="cadet">cadet</option>
                            <option value="specialist">specialist</option>
                            <option value="lieutenant">lieutenant</option>
                            <option value="captain" selected>captain</option>
                            <option value="commander">commander</option>
                            <option value="general">general</option>
                            <option value="admiral">admiral</option>
                        </select>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_command" type="checkbox" checked onchange="syncAdvancedPolicyAwareness()" /> command</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_bossgate_travel_control" type="checkbox" checked onchange="syncAdvancedPolicyAwareness()" /> bossgate_travel_control</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_runtime_observation" type="checkbox" checked /> runtime_observation</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_task_queue_management" type="checkbox" checked /> task_queue_management</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_web_search" type="checkbox" checked /> web_search</label>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_policy_planning" type="checkbox" /> policy_planning</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_memory_sync" type="checkbox" /> memory_sync</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_incident_triage" type="checkbox" /> incident_triage</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_code_review" type="checkbox" /> code_review</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_ui_design" type="checkbox" /> ui_design</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_art_direction" type="checkbox" /> art_direction</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_documentation_crafting" type="checkbox" /> documentation_crafting</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_test_orchestration" type="checkbox" /> test_orchestration</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_security_audit" type="checkbox" /> security_audit</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_performance_tuning" type="checkbox" /> performance_tuning</label>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_data_analysis" type="checkbox" /> data_analysis</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_workflow_automation" type="checkbox" /> workflow_automation</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_customer_support" type="checkbox" /> customer_support</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_integration_mapping" type="checkbox" /> integration_mapping</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="skill_api_composition" type="checkbox" /> api_composition</label>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_transporter" type="checkbox" /> sigil_transporter</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_prime_overwatch" type="checkbox" /> prime_overwatch</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_bind" type="checkbox" /> sigil_bind</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_trace" type="checkbox" /> sigil_trace</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_harmony" type="checkbox" /> sigil_harmony</label>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_prime_foresight" type="checkbox" /> prime_foresight</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_prime_bastion" type="checkbox" /> prime_bastion</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_palette" type="checkbox" /> sigil_palette</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_resonance" type="checkbox" /> sigil_resonance</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_flux" type="checkbox" /> sigil_flux</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_anchor" type="checkbox" /> sigil_anchor</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_lens" type="checkbox" /> sigil_lens</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_weave" type="checkbox" /> sigil_weave</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_echo" type="checkbox" /> sigil_echo</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_guard" type="checkbox" /> sigil_guard</label>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_spark" type="checkbox" /> sigil_spark</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_patch" type="checkbox" /> sigil_patch</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_scribe" type="checkbox" /> sigil_scribe</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_orbit" type="checkbox" /> sigil_orbit</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="sigil_sigil_shield" type="checkbox" /> sigil_shield</label>
                    </div>
                    <div class="row">
                        <input id="maker_custom_skills" placeholder="custom skills (comma-separated, advanced mode)" />
                        <input id="maker_custom_sigils" placeholder="custom sigils (comma-separated, advanced mode)" />
                    </div>
                    <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0;">
                        <div class="muted" style="margin-bottom:8px;">State Machine (Advanced)</div>
                        <div class="row">
                            <select id="maker_state_machine_template" onchange="applySelectedStateMachineTemplate()">
                                <option value="none" selected>state machine: none</option>
                                <option value="basic_lifecycle">state machine: basic lifecycle</option>
                                <option value="delegation_flow">state machine: delegation flow</option>
                                <option value="incident_response">state machine: incident response</option>
                            </select>
                            <button onclick="formatStateMachineJson()">Format JSON</button>
                            <button onclick="clearStateMachineJson()">Clear</button>
                        </div>
                        <div id="maker_state_machine_hint" class="muted" style="margin:6px 0;">No state machine selected. You can paste custom JSON below.</div>
                        <textarea id="maker_state_machine_json" placeholder='{"initial_state":"Idle","states":{"Idle":{"on_task":"Executing"}}}' style="min-height:140px;"></textarea>
                    </div>
                    <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0;">
                        <div class="muted" style="margin-bottom:8px;">Custom Icon (Advanced)</div>
                        <div class="row">
                            <select id="maker_icon_mode" onchange="toggleMakerIconSource()">
                                <option value="none" selected>icon: default</option>
                                <option value="upload">icon: upload file</option>
                                <option value="iconforge">icon: create in IconForge</option>
                            </select>
                            <input id="maker_icon_path" placeholder="custom icon path (.ico)" readonly />
                            <button onclick="clearMakerIconSelection()">Clear Icon</button>
                        </div>
                        <div id="maker_icon_upload_row" class="row" style="display:none; margin-top:6px;">
                            <button onclick="triggerMakerIconUpload()">Upload Icon/Image</button>
                            <span id="maker_icon_upload_name" class="muted">No file selected</span>
                            <input id="maker_icon_upload_file" type="file" style="display:none;" accept=".png" onchange="handleMakerIconUpload(event)" />
                        </div>
                        <div id="maker_iconforge_row" class="row" style="display:none; margin-top:6px;">
                            <input id="maker_icon_label" maxlength="3" value="AG" placeholder="label (max 3)" />
                            <input id="maker_icon_bg" value="#1d3557" placeholder="background color" />
                            <input id="maker_icon_fg" value="#f1faee" placeholder="foreground color" />
                            <button onclick="createMakerIconForge()">Create In IconForge</button>
                            <button onclick="openIconForgeFromAgentForge('advanced')">Open IconForge Session</button>
                        </div>
                        <div id="maker_icon_status" class="muted" style="margin-top:6px;">Using default icon.</div>
                    </div>
                    <div id="maker_policy_chips" class="row" style="flex-wrap:wrap; gap:8px;"></div>
                    <div class="row">
                        <select id="maker_dispatch_scope" onchange="syncAdvancedPolicyAwareness()">
                            <option value="host" selected>dispatch: host</option>
                            <option value="lan">dispatch: lan</option>
                            <option value="remote">dispatch: remote</option>
                        </select>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_dispatch_autonomous" type="checkbox" checked onchange="syncAdvancedPolicyAwareness()" /> autonomous bus intake</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_dispatch_remote_hunt" type="checkbox" onchange="syncAdvancedPolicyAwareness()" /> proactive remote hunt</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_dispatch_leave_without_command" type="checkbox" onchange="syncAdvancedPolicyAwareness()" /> leave host w/o command</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_dispatch_lan_when_idle" type="checkbox" checked onchange="syncAdvancedPolicyAwareness()" /> LAN when host idle</label>
                    </div>
                    <div class="row">
                        <input id="maker_temperature" type="number" min="0" max="2" step="0.05" value="0.2" placeholder="temperature" />
                        <input id="maker_max_tokens" type="number" min="64" max="8192" step="1" value="900" placeholder="max tokens" />
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_has_llm" type="checkbox" checked /> has LLM</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_bossgate_enabled" type="checkbox" checked /> BossGate enabled</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_encrypt_profile" type="checkbox" checked /> Hide proprietary profile details</label>
                        <button onclick="createAgentProfile()">Create/Update</button>
                    </div>
                    <div class="row">
                        <input id="maker_model_source_path" placeholder="complete local model source directory" style="min-width:360px;" />
                        <input id="maker_model_base_source_path" placeholder="adapter base-model directory (optional)" style="min-width:320px;" />
                    </div>
                    <div class="muted">AgentForge leaves the Forge source unchanged and immediately creates a complete, independently owned encrypted model package for the new agent.</div>
                    <pre id="maker_validation" class="muted">Role-aware validation ready.</pre>
                </div>

                <div class="row">
                    <select id="maker_agent_select" onchange="inspectSelectedAgentProfile()"></select>
                    <input id="maker_task" placeholder="task for selected agent" />
                    <select id="maker_override_endpoint"></select>
                    <button onclick="inspectSelectedAgentProfile()">Inspect</button>
                    <button onclick="runAgentProfile()">Run</button>
                    <button onclick="deleteAgentProfile()">Delete</button>
                </div>
                <div class="row">
                    <input id="maker_user" placeholder="user (optional)" />
                    <input id="maker_employer" placeholder="employer (optional)" />
                    <input id="maker_project" placeholder="project (optional)" />
                    <input id="maker_counterpart" placeholder="counterpart agent (optional)" />
                </div>

                <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0;">
                    <div class="muted" style="margin-bottom:8px;">Incident Triage Preview (domain tagging + adaptive priority)</div>
                    <div class="row">
                        <input id="triage_title" placeholder="incident title" />
                        <select id="triage_scope"><option value="">scope auto</option><option value="host">host</option><option value="lan">lan</option><option value="remote">remote</option></select>
                        <input id="triage_urgency" type="number" min="0" max="1" step="0.05" value="0.55" placeholder="urgency" />
                        <input id="triage_risk" type="number" min="0" max="1" step="0.05" value="0.50" placeholder="risk" />
                        <input id="triage_proximity" type="number" min="0" max="1" step="0.05" value="0.70" placeholder="proximity" />
                        <input id="triage_confidence" type="number" min="0" max="1" step="0.05" value="0.60" placeholder="confidence" />
                    </div>
                    <div class="row">
                        <input id="triage_summary" placeholder="incident summary/details" />
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="triage_commanded" type="checkbox" /> explicitly commanded</label>
                        <button onclick="runIncidentTriage()">Tag + Rank Agents</button>
                    </div>
                    <pre id="triage_result">No triage run yet.</pre>
                </div>
                <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin:8px 0; background:linear-gradient(180deg, rgba(16,20,28,0.98), rgba(10,13,19,0.98));">
                    <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin-bottom:8px;">
                        <strong style="color:#8fd3ff; letter-spacing:0.04em;">Selected Agent View</strong>
                        <span id="maker_agent_policy_badge" style="display:inline-flex; align-items:center; padding:4px 10px; border-radius:999px; border:1px solid #4b5563; color:#cbd5e1; font-size:12px;">Awaiting selection</span>
                    </div>
                    <div id="maker_agent_policy" class="muted" style="margin-bottom:8px;">Select an agent to inspect its sealed status or authenticated forge view.</div>
                    <div id="maker_agent_summary" style="border:1px solid #263041; border-radius:12px; padding:12px; margin-bottom:10px; background:radial-gradient(circle at top, rgba(71,118,230,0.14), rgba(8,12,18,0.96));">
                        <div id="maker_agent_summary_title" style="font-size:15px; font-weight:700; color:#dbeafe; margin-bottom:4px;">No agent selected</div>
                        <div id="maker_agent_summary_subtitle" class="muted" style="margin-bottom:10px;">Choose an agent to reveal its package status.</div>
                        <div id="maker_agent_summary_chips" style="display:flex; flex-wrap:wrap; gap:8px; margin-bottom:10px;"></div>
                        <div id="maker_agent_summary_grid" style="display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:8px;"></div>
                    </div>
                    <pre id="maker_agent_view">No agent selected.</pre>
                </div>
                <pre id="maker_result">No agent operation yet.</pre>
            </section>

            <section id="view_iconforge" class="card view-panel">
                <h2 style="color:#ffb27d;">IconForge Studio</h2>
                <div class="muted" style="margin-bottom:8px;">Full-center icon editor for painting, importing, FX, and multi-size .ico export.</div>
                <div class="iconforge-menubar" id="iconforge_menubar">
                    <div class="iconforge-menu" data-iconforge-menu>
                        <button class="iconforge-menu-btn" onclick="toggleIconForgeMenu(this, event)">File</button>
                        <div class="iconforge-menu-list">
                            <button onclick="closeIconForgeMenus(); iconStudioClearCanvas();">New Canvas <span class="menu-shortcut">Ctrl+N</span></button>
                            <button onclick="closeIconForgeMenus(); triggerIconStudioImport();">Import Image... <span class="menu-shortcut">Ctrl+O</span></button>
                            <div class="iconforge-menu-sep"></div>
                            <button onclick="closeIconForgeMenus(); saveIconStudioDraft();">Save Draft <span class="menu-shortcut">Ctrl+S</span></button>
                            <button onclick="closeIconForgeMenus(); loadIconStudioDraft();">Load Draft <span class="menu-shortcut">Ctrl+Shift+L</span></button>
                            <button onclick="closeIconForgeMenus(); clearIconStudioDraft();">Clear Draft</button>
                            <div class="iconforge-menu-sep"></div>
                            <button onclick="closeIconForgeMenus(); downloadIconStudioPng();">Export PNG <span class="menu-shortcut">Ctrl+Shift+P</span></button>
                            <button onclick="closeIconForgeMenus(); saveIconStudioIco();">Export .ico (16-256) <span class="menu-shortcut">Ctrl+Shift+S</span></button>
                            <button onclick="closeIconForgeMenus(); saveIconStudioAnimated();">Export Animated GIF <span class="menu-shortcut">Ctrl+Shift+G</span></button>
                        </div>
                    </div>
                    <div class="iconforge-menu" data-iconforge-menu>
                        <button class="iconforge-menu-btn" onclick="toggleIconForgeMenu(this, event)">Edit</button>
                        <div class="iconforge-menu-list">
                            <button onclick="closeIconForgeMenus(); iconStudioUndoStroke();">Undo Stroke <span class="menu-shortcut">Ctrl+Z</span></button>
                            <button onclick="closeIconForgeMenus(); iconStudioFillBackground();">Fill Background</button>
                            <button onclick="closeIconForgeMenus(); iconStudioClearCanvas();">Clear Canvas <span class="menu-shortcut">Ctrl+L</span></button>
                        </div>
                    </div>
                    <div class="iconforge-menu" data-iconforge-menu>
                        <button class="iconforge-menu-btn" onclick="toggleIconForgeMenu(this, event)">FX</button>
                        <div class="iconforge-menu-list">
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('grayscale');">Grayscale <span class="menu-shortcut">Ctrl+Shift+1</span></button>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('invert');">Invert <span class="menu-shortcut">Ctrl+I</span></button>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('contrast');">Contrast+ <span class="menu-shortcut">Ctrl+Shift+C</span></button>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('soften');">Soften</button>
                            <div class="iconforge-menu-sep"></div>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('glow_soft');">Glow Soft</button>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('glow_neon');">Glow Neon</button>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('swirl_warp');">Swirl Warp</button>
                            <button onclick="closeIconForgeMenus(); applyIconStudioFx('particle_swirl');">Particle Swirl</button>
                        </div>
                    </div>
                    <div class="iconforge-menu" data-iconforge-menu>
                        <button class="iconforge-menu-btn" onclick="toggleIconForgeMenu(this, event)">View</button>
                        <div class="iconforge-menu-list">
                            <button onclick="closeIconForgeMenus(); refreshIconForgeOps();">Refresh Backups</button>
                            <button onclick="closeIconForgeMenus(); refreshWindowsIconCache();">Refresh Icon Cache</button>
                            <button onclick="closeIconForgeMenus(); setIconStudioStatus('IconForge menus are active.');">Status Ping</button>
                        </div>
                    </div>
                    <div class="iconforge-menu" data-iconforge-menu>
                        <button class="iconforge-menu-btn" onclick="toggleIconForgeMenu(this, event)">Windows Ops</button>
                        <div class="iconforge-menu-list">
                            <button onclick="closeIconForgeMenus(); setIconForgeFromStudioIco();">Use Latest Studio ICO</button>
                            <button onclick="closeIconForgeMenus(); applyWindowsIconOverride();">Apply Icon Override</button>
                            <button onclick="closeIconForgeMenus(); restoreWindowsIconOverride();">Restore Backup</button>
                            <div class="iconforge-menu-sep"></div>
                            <button onclick="closeIconForgeMenus(); exportIconForgePack();">Export Icon Pack</button>
                            <button onclick="closeIconForgeMenus(); importIconForgePack();">Import Icon Pack</button>
                        </div>
                    </div>
                    <div class="iconforge-menu" data-iconforge-menu>
                        <button class="iconforge-menu-btn" onclick="toggleIconForgeMenu(this, event)">Help</button>
                        <div class="iconforge-menu-list">
                            <button onclick="closeIconForgeMenus(); setIconStudioStatus('File menu: import/export. FX menu: visual transforms. Windows Ops: apply/restore icon overrides.');">Show Quick Help</button>
                        </div>
                    </div>
                </div>
                <div id="iconforge_schematics_panel" class="iconforge-schematics">
                    <div class="iconforge-schematics-head">
                        <div>
                            <strong style="color:#f2cf86;">Icon Schematics Map</strong>
                            <div class="muted">Grid of active icon targets and where each icon is applied. Click any tile to edit/change that icon.</div>
                        </div>
                        <div class="row">
                            <button onclick="refreshIconForgeSchematics()">Refresh Map</button>
                            <button onclick="openIconForgeEditorFromSchematic('new')">New Icon</button>
                        </div>
                    </div>
                    <div id="iconforge_schematics_stats" class="muted" style="margin-bottom:8px;">Loading schematics...</div>
                    <div id="iconforge_schematics_grid" class="iconforge-schematics-grid"></div>
                </div>
                <div id="iconforge_editor_panel" class="workspace-grid" style="display:none;">
                    <div class="workspace-pane workspace-stack">
                        <h3>Studio Controls</h3>
                        <div class="row">
                            <button onclick="showIconForgeSchematics()">Back To Icon Schematics</button>
                            <span id="iconforge_editor_context" class="muted">No target selected.</span>
                        </div>
                        <div class="row">
                            <select id="icon_studio_tool">
                                <option value="brush" selected>tool: brush</option>
                                <option value="eraser">tool: eraser</option>
                            </select>
                            <input id="icon_studio_color" type="color" value="#d4a857" />
                            <input id="icon_studio_size" type="range" min="1" max="48" step="1" value="10" />
                            <span id="icon_studio_size_label" class="muted">10px</span>
                        </div>
                        <div class="row">
                            <input id="icon_studio_name" placeholder="icon file stem" value="agent_forge_icon" />
                        </div>
                        <div class="row" id="icon_studio_agentforge_row" style="display:none;">
                            <select id="icon_studio_target">
                                <option value="standalone" selected>apply: standalone only</option>
                                <option value="wizard">apply to wizard</option>
                                <option value="advanced">apply to advanced</option>
                                <option value="both">apply to both</option>
                            </select>
                        </div>
                        <div id="icon_studio_agentforge_hint" class="muted" style="display:none;">AgentForge session active.</div>
                        <div style="border:1px solid #2b2f3a; border-radius:10px; padding:8px; margin-top:6px;">
                            <div class="muted" style="margin-bottom:6px;">Layers</div>
                            <div class="row">
                                <input id="icon_studio_layer_name" placeholder="active layer name" />
                                <button onclick="iconStudioRenameActiveLayer()">Rename</button>
                            </div>
                            <div class="row">
                                <label class="muted" style="display:flex; align-items:center; gap:6px;">blend
                                    <select id="icon_studio_layer_blend" onchange="iconStudioSetActiveLayerBlend(this.value)">
                                        <option value="source-over" selected>normal</option>
                                        <option value="multiply">multiply</option>
                                        <option value="screen">screen</option>
                                        <option value="overlay">overlay</option>
                                        <option value="soft-light">soft light</option>
                                        <option value="hard-light">hard light</option>
                                        <option value="color-dodge">color dodge</option>
                                        <option value="color-burn">color burn</option>
                                        <option value="lighten">lighten</option>
                                        <option value="darken">darken</option>
                                    </select>
                                </label>
                            </div>
                            <div class="row">
                                <label class="muted" style="display:flex; align-items:center; gap:6px;">opacity
                                    <input id="icon_studio_layer_opacity" type="range" min="0" max="100" step="1" value="100" oninput="iconStudioSetActiveLayerOpacity(this.value)" />
                                </label>
                                <span id="icon_studio_layer_opacity_label" class="muted">100%</span>
                            </div>
                            <div class="row">
                                <button onclick="iconStudioAddLayer()">Add Layer</button>
                                <button onclick="iconStudioDuplicateLayer()">Duplicate</button>
                                <button onclick="iconStudioDeleteLayer()">Delete</button>
                                <button onclick="iconStudioMoveLayer(-1)">Up</button>
                                <button onclick="iconStudioMoveLayer(1)">Down</button>
                                <button onclick="iconStudioToggleActiveLayerVisibility()">Toggle Visible</button>
                            </div>
                            <div id="icon_studio_layer_list" class="muted" style="max-height:120px; overflow:auto; border:1px solid #2b2f3a; border-radius:8px; padding:6px;">No layers yet.</div>
                        </div>
                        <div style="border:1px solid #2b2f3a; border-radius:10px; padding:8px; margin-top:6px;">
                            <div class="muted" style="margin-bottom:6px;">FX Control</div>
                            <div class="row">
                                <label class="muted" style="display:flex; align-items:center; gap:6px;">strength
                                    <input id="icon_fx_strength" type="range" min="1" max="100" step="1" value="55" />
                                </label>
                                <span id="icon_fx_strength_label" class="muted">55%</span>
                            </div>
                            <div class="row">
                                <label class="muted" style="display:flex; align-items:center; gap:6px;">passes
                                    <input id="icon_fx_passes" type="range" min="1" max="5" step="1" value="1" />
                                </label>
                                <span id="icon_fx_passes_label" class="muted">1x</span>
                            </div>
                        </div>
                        <input id="icon_studio_import_file" type="file" style="display:none;" accept=".png" onchange="handleIconStudioImport(event)" />
                        <div class="row">
                            <select id="icon_studio_anim_preset">
                                <option value="pulse" selected>anim: pulse</option>
                                <option value="spin">anim: spin</option>
                                <option value="shimmer">anim: shimmer</option>
                            </select>
                            <input id="icon_studio_anim_seconds" type="number" min="1" max="12" step="1" value="3" placeholder="seconds" />
                            <input id="icon_studio_anim_fps" type="number" min="6" max="30" step="1" value="12" placeholder="fps" />
                        </div>
                        <div class="muted">Use the menu bar for File, Edit, FX, View, and Windows operations.</div>
                        <div id="icon_studio_status" class="muted">Studio ready.</div>
                    </div>

                    <div class="workspace-pane workspace-stack">
                        <h3>Canvas + Operations</h3>
                        <div class="workspace-canvas-wrap">
                            <canvas id="icon_studio_canvas" width="256" height="256" style="width:256px; height:256px; border:1px solid #3c4559; border-radius:10px; background:linear-gradient(45deg, rgba(255,255,255,0.06) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.06) 75%), linear-gradient(45deg, rgba(255,255,255,0.06) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.06) 75%); background-size:16px 16px; background-position:0 0, 8px 8px; cursor:crosshair;"></canvas>

                            <div class="workspace-canvas-controls">
                                <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px;">
                                    <div class="muted" style="margin-bottom:8px;">Windows Icon Operations (replace system icons + icon packs)</div>
                                    <div class="row">
                                        <select id="iconforge_target_type">
                                            <option value="folder" selected>target: folder path</option>
                                            <option value="shortcut">target: shortcut (.lnk)</option>
                                            <option value="file_extension">target: file extension (e.g. .txt)</option>
                                            <option value="application">target: application (e.g. notepad.exe)</option>
                                            <option value="drive">target: drive letter (e.g. C or D:)</option>
                                        </select>
                                        <input id="iconforge_target_value" placeholder="target value" />
                                        <input id="iconforge_icon_path" placeholder="icon path (.ico)" />
                                    </div>
                                    <div class="row">
                                        <input id="iconforge_restore_key" placeholder="backup key to restore" />
                                    </div>
                                    <div class="row">
                                        <input id="iconforge_pack_export_dir" placeholder="export pack directory path" />
                                    </div>
                                    <div class="row">
                                        <input id="iconforge_pack_import_source" placeholder="import pack source (dir or icon_set_manifest.json path)" />
                                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="iconforge_pack_apply" type="checkbox" checked /> apply changes</label>
                                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="iconforge_pack_refresh" type="checkbox" checked /> refresh cache</label>
                                    </div>
                                    <div class="muted">Run these operations from the Windows Ops menu.</div>
                                    <pre id="iconforge_ops_result">No icon operations yet.</pre>
                                </div>

                                <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px;">
                                    <div class="muted" style="margin-bottom:8px;">Backup Catalog</div>
                                    <pre id="iconforge_backups">No backups loaded.</pre>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </section>

            <section id="view_security" class="card view-panel">
                <h2>Security</h2>
                <div class="row"><input id="security_scan_path" placeholder="scan path (blank = workspace)" /><button onclick="runSecurityScan()">Run Scan</button><button onclick="refreshSecurityState()">Refresh State</button></div>
                <pre id="security_findings">Loading...</pre>
                <div class="row"><button onclick="refreshSecretsList()">Refresh Secret Keys</button></div>
                <pre id="security_secrets">No secrets loaded.</pre>
            </section>


            <section id="view_onboarding" class="card view-panel">
                <h2 style="color:#f2c96b;">Onboarding Wizard</h2>
                <div class="muted">Guide for initial setup: secrets, tokens, and voice profile.</div>
                <div class="row" style="margin-top:8px;">
                    <button onclick="runOnboardingStep('workspace_check')">Run Workspace Check</button>
                    <button onclick="runOnboardingStep('security_baseline')">Mark Security Baseline Complete</button>
                    <button onclick="runOnboardingStep('model_gateway')">Mark Model Gateway Complete</button>
                    <button onclick="refreshOnboardingStatus()">Refresh</button>
                </div>
                <pre id="onboarding_status" style="margin-top:12px;">Loading onboarding status...</pre>
            </section>

            <section id="view_scheduler" class="card view-panel">
                <h2 style="color:#f2c96b;">Scheduler</h2>
                <div class="muted">Panel for scheduling tasks and rituals.</div>
                <div class="row" style="margin-top:8px;">
                    <input id="scheduler_label" placeholder="job label" />
                    <input id="scheduler_command" placeholder="shell command (optional)" />
                    <input id="scheduler_interval" type="number" min="30" value="300" placeholder="interval seconds" />
                    <button onclick="addSchedulerJob()">Add Job</button>
                    <button onclick="refreshSchedulerStatus()">Refresh</button>
                </div>
                <div class="row" style="margin-top:8px;">
                    <input id="scheduler_remove_id" placeholder="job id to remove" />
                    <button onclick="removeSchedulerJob()">Remove Job</button>
                    <input id="scheduler_run_id" placeholder="job id to run now" />
                    <button onclick="runSchedulerJobNow()">Run Job Now</button>
                </div>
                <pre id="scheduler_status" style="margin-top:12px;">Loading scheduler status...</pre>
            </section>

            <section id="view_cicd" class="card view-panel">
                <h2 style="color:#57d183;">CI/CD</h2>
                <div class="muted">Panel for test/lint results and CI status.</div>
                <div class="row" style="margin-top:8px;">
                    <select id="cicd_suite">
                        <option value="quick">Quick Validation</option>
                        <option value="full">Full Unit Suite</option>
                    </select>
                    <button onclick="runCicdPipeline()">Run Pipeline</button>
                    <button onclick="refreshCicdStatus()">Refresh</button>
                </div>
                <pre id="cicd_status" style="margin-top:12px;">Loading CI/CD status...</pre>
            </section>
        </main>
    </div>

    <script>
        let currentView = 'view_status';
        let chatHistory = [];
        let pinnedOverlayViewId = '';
        let soundEvents = [];
        let soundScheme = {};
        let pendingLoads = 0;
        let discoveryTargets = [];
        let discoveryLocations = {};
        let activeDiscoveryKey = '';
        let snapshotGaugeBooted = false;
        let snapshotDiskIoLast = {};
        let snapshotDiskIoLastTs = 0;
        let previousOsState = null;
        let busLiveTimer = null;
        let iconStudioCtx = null;
        let iconStudioDrawing = false;
        let iconStudioUndo = [];
        let iconStudioBooted = false;
        let iconStudioLayers = [];
        let iconStudioActiveLayer = 0;
        let iconStudioDraggingLayer = -1;
        let iconStudioLayerSeed = 1;
        let iconForgeSchematics = [];
        let iconForgeBackupsCache = {};
        let iconForgeVisited = false;
        let iconForgeSectionCollapseState = {};
        let iconForgeAgentContext = { active: false, source: '', agentName: '' };
        let wizardStep = 1;
        const WIZARD_TOTAL_STEPS = 4;
        const ICON_STUDIO_DRAFT_KEY = 'bossforge.iconforge.studio.v1';
        const PRODUCT_MODE_CONFIG = {
            iconforge: {
                title: 'IconForge',
                subtitle: 'Standalone Edition',
                hallTitle: 'IconForge Studio',
                hallSubtitle: 'Standalone icon design and Windows icon operations workspace.',
                defaultView: 'view_iconforge',
                allowedViews: ['view_iconforge'],
            },
            soundforge: {
                title: 'SoundForge',
                subtitle: 'Standalone Edition',
                hallTitle: 'SoundForge Console',
                hallSubtitle: 'Standalone sound scheme editor and bundle operations workspace.',
                defaultView: 'view_sounds',
                allowedViews: ['view_sounds'],
            },
        };

        function showJsError(message) {
            const root = document.getElementById('js_error');
            if (!root) return;
            root.textContent = String(message || 'Unknown JavaScript error');
            root.classList.add('active');
        }

        function clearJsError() {
            const root = document.getElementById('js_error');
            if (!root) return;
            root.textContent = '';
            root.classList.remove('active');
        }

        function wireInlineClickFallback() {
            // Keep native inline handlers untouched; some environments block eval-style execution.
        }

        window.addEventListener('error', (event) => {
            const msg = event && event.message ? event.message : 'Unknown JavaScript error';
            showJsError('Runtime error: ' + msg);
        });

        window.addEventListener('unhandledrejection', (event) => {
            const reason = event && event.reason ? String(event.reason) : 'Unhandled promise rejection';
            showJsError('Async error: ' + reason);
        });

        function beginBusy(message) {
            pendingLoads += 1;
            const root = document.getElementById('busy_indicator');
            const text = document.getElementById('busy_text');
            if (!root || !text) return;
            if (message) text.textContent = message;
            root.classList.add('active');
        }

        function endBusy() {
            pendingLoads = Math.max(0, pendingLoads - 1);
            const root = document.getElementById('busy_indicator');
            const text = document.getElementById('busy_text');
            if (!root || !text) return;
            if (pendingLoads === 0) {
                root.classList.remove('active');
                text.textContent = 'Loading...';
            }
        }

        async function refreshDiagnostics() {
            const el = document.getElementById('diagnostics_output');
            if (!el) return;
            el.textContent = 'Loading...';

            const statusData = await fetchJsonWithTimeout('/api/status');
            const eventsData = await fetchJsonWithTimeout('/api/events?limit=20');
            const lines = [];

            const agentState = (statusData && statusData.agent_state && typeof statusData.agent_state === 'object')
                ? statusData.agent_state
                : {};
            const names = Object.keys(agentState);
            lines.push('Agent Health:');
            if (names.length) {
                for (const name of names) {
                    const info = agentState[name] || {};
                    lines.push('- ' + name + ': ' + (info.health || 'unknown') + ' (last seen: ' + (info.last_seen || 'never') + ')');
                }
            } else {
                lines.push('- No agent health data available.');
            }

            lines.push('');
            lines.push('Recent Events:');
            const events = (eventsData && Array.isArray(eventsData.items)) ? eventsData.items : [];
            if (events.length) {
                for (const item of events.slice(0, 10)) {
                    const stamp = item && item.timestamp ? String(item.timestamp) : 'unknown-time';
                    const evt = item && (item.event || item.type) ? String(item.event || item.type) : 'event';
                    lines.push('- ' + stamp + ' :: ' + evt);
                }
            } else {
                lines.push('- No events available.');
            }

            el.textContent = lines.join('\\n');
        }

        function htmlEscape(value) {
            return String(value || '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        }

        function stableHash(input) {
            const text = String(input || '');
            let hash = 2166136261;
            for (let i = 0; i < text.length; i += 1) {
                hash ^= text.charCodeAt(i);
                hash += (hash << 1) + (hash << 4) + (hash << 7) + (hash << 8) + (hash << 24);
            }
            return Math.abs(hash >>> 0);
        }

        function targetKey(target) {
            const node = (target.node_id || target.current_node || target.address || 'node').trim();
            const agent = (target.agent_name || '').trim();
            return node + '::' + agent;
        }

        function targetPinClass(target) {
            if (target.assistance_requested) return 'assist';
            if (target.allowed_for_transfer) return 'available';
            return 'remote';
        }

        function renderDiscoveryLoadout(target) {
            const root = document.getElementById('discovery_loadout');
            if (!root) return;
            if (!target) {
                root.innerHTML = '<span class="muted">Select a pin to inspect its loadout.</span>';
                return;
            }
            const lines = [
                ['Agent', target.agent_name || '(node-level target)'],
                ['Node', target.node_id || target.current_node || '(unknown)'],
                ['Address', target.address || '(unknown)'],
                ['Creator Node', target.created_by_node || '(unspecified)'],
                ['Current Node', target.current_node || target.node_id || '(unspecified)'],
                ['Target Type', target.target_type || '(unknown)'],
                ['Agent Class', target.agent_class || '(unknown)'],
                ['Travel Eligible', target.allowed_for_transfer ? 'yes' : 'no'],
                ['Assistance Requested', target.assistance_requested ? 'yes' : 'no'],
                ['Assistance Reason', target.assistance_reason || '(none)'],
                ['Source', target.source || target.reason || '(discovery)'],
            ];
            root.innerHTML = lines.map((pair) => '<div><strong>' + htmlEscape(pair[0]) + ':</strong> ' + htmlEscape(pair[1]) + '</div>').join('');
        }

        function renderDiscoveryMapPins() {
            const map = document.getElementById('discovery_map');
            const summary = document.getElementById('discovery_summary');
            if (!map || !summary) return;

            map.querySelectorAll('.map-pin').forEach((el) => el.remove());

            const all = Array.isArray(discoveryTargets) ? discoveryTargets : [];
            summary.textContent = all.length ? (all.length + ' target(s) mapped') : 'No targets discovered yet';

            if (!all.length) {
                renderDiscoveryLoadout(null);
                return;
            }

            all.forEach((target, idx) => {
                const key = targetKey(target);
                const seed = stableHash(key + ':' + idx);
                const x = 8 + (seed % 84);
                const y = 16 + (Math.floor(seed / 101) % 74);

                const pin = document.createElement('button');
                pin.className = 'map-pin ' + targetPinClass(target);
                if (activeDiscoveryKey === key) pin.classList.add('active');
                pin.style.left = x + '%';
                pin.style.top = y + '%';
                pin.title = (target.agent_name || target.node_id || target.address || 'target') + ' [' + (target.target_type || 'unknown') + ']';
                pin.setAttribute('aria-label', pin.title);
                pin.onclick = () => {
                    activeDiscoveryKey = key;
                    renderDiscoveryMapPins();
                    renderDiscoveryLoadout(target);
                };
                map.appendChild(pin);
            });

            const selected = all.find((t) => targetKey(t) === activeDiscoveryKey) || all[0];
            activeDiscoveryKey = targetKey(selected);
            renderDiscoveryLoadout(selected);
            map.querySelectorAll('.map-pin').forEach((el) => {
                if (el.title.startsWith((selected.agent_name || selected.node_id || selected.address || ''))) {
                    el.classList.add('active');
                }
            });
        }

        function mergeDiscoveryData(targets, locations) {
            const merged = [];
            const seen = new Set();
            for (const item of (Array.isArray(targets) ? targets : [])) {
                const key = targetKey(item);
                if (seen.has(key)) continue;
                seen.add(key);
                merged.push(item);
            }
            if (locations && typeof locations === 'object') {
                for (const [name, loc] of Object.entries(locations)) {
                    if (!loc || typeof loc !== 'object') continue;
                    const item = {
                        agent_name: name,
                        address: loc.address || '',
                        node_id: loc.node_id || loc.current_node || '',
                        current_node: loc.current_node || loc.node_id || '',
                        created_by_node: loc.created_by_node || '',
                        target_type: loc.target_type || 'bossforgeos',
                        agent_class: loc.agent_class || 'prime',
                        assistance_requested: !!loc.assistance_requested,
                        assistance_reason: loc.assistance_reason || '',
                        allowed_for_transfer: loc.target_type ? true : !!loc.online,
                        source: loc.source || 'owned-location-ledger',
                    };
                    const key = targetKey(item);
                    if (seen.has(key)) continue;
                    seen.add(key);
                    merged.push(item);
                }
            }
            return merged;
        }

        async function refreshOwnedLocations() {
            const data = await fetchJsonWithTimeout('/api/model/agents/locations?refresh=true', 5000);
            discoveryLocations = (data && data.ok && data.agents && typeof data.agents === 'object') ? data.agents : {};
            discoveryTargets = mergeDiscoveryData(discoveryTargets, discoveryLocations);
            const raw = document.getElementById('discovery_raw');
            if (raw) raw.textContent = JSON.stringify({ targets: discoveryTargets, locations: discoveryLocations }, null, 2);
            renderDiscoveryMapPins();
        }

        async function refreshDiscoveryMap() {
            const assistanceOnly = !!document.getElementById('discovery_assistance_only')?.checked;
            const data = await fetchJsonWithTimeout('/api/model/travel/discover?timeout=5&operator_id=' + encodeURIComponent(bossGateCurrentUser()) + '&scope_id=bossgate-map-read&assistance_only=' + (assistanceOnly ? 'true' : 'false'), 5000);
            const discovered = (data && data.ok && Array.isArray(data.targets)) ? data.targets : [];
            const locationsData = await fetchJsonWithTimeout('/api/model/agents/locations?refresh=true', 5000);
            discoveryLocations = (locationsData && locationsData.ok && locationsData.agents && typeof locationsData.agents === 'object') ? locationsData.agents : {};
            discoveryTargets = mergeDiscoveryData(discovered, discoveryLocations);

            const raw = document.getElementById('discovery_raw');
            if (raw) {
                raw.textContent = JSON.stringify(
                    {
                        discover_response: data,
                        owned_locations: discoveryLocations,
                        merged_targets: discoveryTargets,
                    },
                    null,
                    2
                );
            }
            renderDiscoveryMapPins();
        }

        async function refreshBossGateMap(refreshRemote = true) {
            const data = await fetchJsonWithTimeout('/api/model/travel/map?refresh=' + (refreshRemote ? 'true' : 'false') + '&timeout=3', 5000);
            const transferData = await fetchJsonWithTimeout('/api/model/travel/transfers?limit=25', 5000);
            const raw = document.getElementById('bossgate_map_raw');
            const summary = document.getElementById('bossgate_map_summary');
            const transfers = (transferData && transferData.ok && Array.isArray(transferData.items)) ? transferData.items : [];
            if (raw) raw.textContent = JSON.stringify({ map: data, transfers }, null, 2);
            const map = (data && data.ok && data.map && typeof data.map === 'object') ? data.map : {};
            const gateCount = Array.isArray(map.gates) ? map.gates.length : 0;
            const travelableCount = Array.isArray(map.travelable_gates) ? map.travelable_gates.length : 0;
            const agentCount = map.agents && typeof map.agents === 'object' ? Object.keys(map.agents).length : 0;
            if (summary) summary.textContent = `gates: ${gateCount} | travelable: ${travelableCount} | agents: ${agentCount} | transfers: ${transfers.length}`;
            renderBossGateTopology(map, transfers);
        }

        function escapeHtml(value) {
            return String(value ?? '')
                .replaceAll('&', '&amp;')
                .replaceAll('<', '&lt;')
                .replaceAll('>', '&gt;')
                .replaceAll('"', '&quot;')
                .replaceAll("'", '&#39;');
        }

        function _hostFromAddress(address) {
            const raw = String(address || '').trim();
            if (!raw) return '';
            try {
                const u = new URL(raw);
                return u.hostname || raw;
            } catch (_) {
                const lowered = raw.toLowerCase();
                let trimmed = raw;
                if (lowered.startsWith('http://')) trimmed = raw.slice(7);
                else if (lowered.startsWith('https://')) trimmed = raw.slice(8);
                return trimmed.split('/')[0];
            }
        }

        const bossGatePresenceState = {
            nodes: [],
            agents: [],
            selected: null,
        };

        function _bossGatePresenceKey(kind, id) {
            return `${String(kind || '')}:${String(id || '')}`;
        }

        function renderBossGatePresenceCard(presence) {
            if (!presence || typeof presence !== 'object') {
                return '<div class="topology-empty">Select a BossGate presence to inspect it.</div>';
            }
            if (presence.presence_kind === 'agent') {
                const card = presence.model_card && typeof presence.model_card === 'object' ? presence.model_card : {};
                return `
                    <div class="bossgate-presence-card bossgate-color-${escapeHtml(presence.color || 'grey')}">
                        <div class="bossgate-presence-title">${escapeHtml(presence.agent_name || 'unknown agent')}</div>
                        <div class="bossgate-presence-subtitle">Model card only while abroad. Return to the origin forge for full inspection.</div>
                        <div class="bossgate-presence-grid">
                            <div class="bossgate-presence-grid-item"><strong>Trust</strong>${escapeHtml(presence.trust_state || 'unknown')}</div>
                            <div class="bossgate-presence-grid-item"><strong>Class</strong>${escapeHtml(card.agent_class || presence.public_identity_card?.agent_class || 'n/a')}</div>
                            <div class="bossgate-presence-grid-item"><strong>Type</strong>${escapeHtml(card.agent_type || presence.public_identity_card?.agent_type || 'n/a')}</div>
                            <div class="bossgate-presence-grid-item"><strong>Rank</strong>${escapeHtml(card.rank || presence.public_identity_card?.rank || 'n/a')}</div>
                        </div>
                    </div>
                `;
            }
            if (presence.discovery_state === 'unrevealed_beacon') {
                return `
                    <div class="bossgate-presence-card bossgate-color-grey">
                        <div class="bossgate-presence-title">Unrevealed Beacon</div>
                        <div class="bossgate-presence-subtitle">Neutral or unaffiliated presence. Identity remains hidden until an actual visit resolves it.</div>
                        <div class="bossgate-presence-grid">
                            <div class="bossgate-presence-grid-item"><strong>Trust</strong>${escapeHtml(presence.trust_state || 'neutral_unaffiliated')}</div>
                            <div class="bossgate-presence-grid-item"><strong>Status</strong>Beacon only</div>
                            <div class="bossgate-presence-grid-item"><strong>Reveal</strong>Visit required</div>
                        </div>
                    </div>
                `;
            }
            return `
                <div class="bossgate-presence-card bossgate-color-${escapeHtml(presence.color || 'grey')}">
                    <div class="bossgate-presence-title">${escapeHtml(presence.display_name || presence.node_id || 'node')}</div>
                    <div class="bossgate-presence-subtitle">${escapeHtml(presence.public_summary || 'Known node presence')}</div>
                    <div class="bossgate-presence-grid">
                        <div class="bossgate-presence-grid-item"><strong>Trust</strong>${escapeHtml(presence.trust_state || 'unknown')}</div>
                        <div class="bossgate-presence-grid-item"><strong>Type</strong>${escapeHtml(presence.node_type || 'unknown')}</div>
                        <div class="bossgate-presence-grid-item"><strong>Discovery</strong>${escapeHtml(presence.discovery_state || 'revealed')}</div>
                    </div>
                </div>
            `;
        }

        function renderBossGateRadialMenu(presence, x, y) {
            if (!presence) return '';
            const actions = presence.presence_kind === 'agent'
                ? ['Send Message', 'Recall Home', 'Route Orders', 'View Model Card', 'Hold / Quarantine', 'Trade History']
                : (presence.discovery_state === 'unrevealed_beacon'
                    ? ['Visit Beacon', 'Allow Unknown Messaging']
                    : ['Send Message', 'Open Node Card', 'Trade History']);
            const angleStep = (Math.PI * 2) / Math.max(actions.length, 1);
            const radius = 74;
            const buttons = actions.map((label, idx) => {
                const angle = (-Math.PI / 2) + (idx * angleStep);
                const left = 110 + (radius * Math.cos(angle)) - 37;
                const top = 110 + (radius * Math.sin(angle)) - 37;
                return `<button class="bossgate-radial-action" style="left:${left}px; top:${top}px;">${escapeHtml(label)}</button>`;
            }).join('');
            const centerLabel = presence.presence_kind === 'agent'
                ? escapeHtml(presence.agent_name || 'agent')
                : escapeHtml(presence.display_name || presence.node_id || 'beacon');
            return `
                <div class="bossgate-radial-menu" style="left:${x}px; top:${y}px;">
                    ${buttons}
                    <div class="bossgate-radial-center bossgate-color-${escapeHtml(presence.color || 'grey')}">${centerLabel}</div>
                </div>
            `;
        }

        function selectBossGatePresence(kind, id, x, y) {
            const key = _bossGatePresenceKey(kind, id);
            const all = [
                ...bossGatePresenceState.nodes,
                ...bossGatePresenceState.agents,
            ];
            const presence = all.find((item) => _bossGatePresenceKey(item.presence_kind, item.node_id || item.agent_name || item.agent_id) === key) || null;
            bossGatePresenceState.selected = presence;
            const card = document.getElementById('bossgate_presence_card');
            const overlay = document.getElementById('bossgate_topology_overlay');
            if (card) card.innerHTML = renderBossGatePresenceCard(presence);
            if (overlay) overlay.innerHTML = renderBossGateRadialMenu(presence, x, y);
        }

        function renderBossGateTopology(map, transfers = []) {
            const root = document.getElementById('bossgate_topology');
            if (!root) return;
            const gates = Array.isArray(map && map.gates) ? map.gates : [];
            const travelable = Array.isArray(map && map.travelable_gates) ? map.travelable_gates : [];
            const agents = Array.isArray(map && map.agents) ? map.agents : [];
            const nodePresences = Array.isArray(map && map.node_presences) ? map.node_presences : [];
            const agentPresences = Array.isArray(map && map.agent_presences) ? map.agent_presences : [];
            const travelableSet = new Set(travelable.map((item) => String(item && (item.address || item.destination || item.endpoint || '')).trim()).filter(Boolean));

            if (!gates.length) {
                root.innerHTML = '<div class="topology-empty">No discovered gates in current snapshot.</div>';
                return;
            }

            const byGate = {};
            for (const agent of agents) {
                if (!agent || typeof agent !== 'object') continue;
                const name = String(agent.agent_name || '').trim().toLowerCase();
                const node = String(agent.current_node || agent.node_id || '').trim();
                if (!node) continue;
                if (!byGate[node]) byGate[node] = [];
                byGate[node].push(name);
            }
            const nodes = gates.map((gate) => {
                const nodeId = String(gate && (gate.node_id || gate.name || gate.id || 'unknown')).trim() || 'unknown';
                const address = String(gate && (gate.address || gate.endpoint || '')).trim();
                const type = String(gate && gate.target_type || 'bossgate_connector').trim();
                const nodePresence = nodePresences.find((item) => String(item && item.node_id || '').trim() === nodeId) || null;
                return {
                    id: nodeId,
                    label: nodeId,
                    address,
                    host: _hostFromAddress(address),
                    type,
                    travelable: !!(address && travelableSet.has(address)),
                    agents: byGate[nodeId] || [],
                    external: false,
                    presence: nodePresence,
                };
            });
            const nodeById = Object.fromEntries(nodes.map((n) => [n.id, n]));
            const nodeByAddress = Object.fromEntries(nodes.filter((n) => n.address).map((n) => [n.address, n]));
            const nodeByHost = Object.fromEntries(nodes.filter((n) => n.host).map((n) => [n.host, n]));
            bossGatePresenceState.nodes = nodePresences;
            bossGatePresenceState.agents = agentPresences;

            const edgeItems = [];
            for (const t of transfers) {
                if (!t || typeof t !== 'object') continue;
                const sourceId = String(t.node_id || '').trim();
                const destination = String(t.destination || '').trim();
                if (!sourceId || !destination) continue;
                let target = nodeByAddress[destination] || nodeByHost[_hostFromAddress(destination)];
                if (!target) {
                    const extId = `external:${_hostFromAddress(destination) || destination}`;
                    if (!nodeById[extId]) {
                        nodeById[extId] = {
                            id: extId,
                            label: _hostFromAddress(destination) || destination,
                            address: destination,
                            host: _hostFromAddress(destination),
                            type: "external",
                            travelable: false,
                            agents: [],
                            external: true,
                        };
                        nodes.push(nodeById[extId]);
                    }
                    target = nodeById[extId];
                }
                if (!nodeById[sourceId]) {
                    nodeById[sourceId] = {
                        id: sourceId,
                        label: sourceId,
                        address: "",
                        host: "",
                        type: "source",
                        travelable: false,
                        agents: [],
                        external: true,
                    };
                    nodes.push(nodeById[sourceId]);
                }
                edgeItems.push({
                    from: sourceId,
                    to: target.id,
                    status: String(t.status || "unknown"),
                    dryRun: !!t.dry_run,
                    timestamp: Number(t.timestamp || 0),
                });
            }

            const width = 980;
            const height = 420;
            const cx = width / 2;
            const cy = height / 2;
            const radius = Math.max(120, Math.min(width, height) * 0.34);
            const total = Math.max(nodes.length, 1);
            const pos = {};
            nodes.forEach((n, idx) => {
                const ang = (Math.PI * 2 * idx) / total - (Math.PI / 2);
                pos[n.id] = { x: cx + radius * Math.cos(ang), y: cy + radius * Math.sin(ang) };
            });

            const edgeSvg = edgeItems.map((edge) => {
                const a = pos[edge.from];
                const b = pos[edge.to];
                if (!a || !b) return '';
                const color = edge.status === "transfer_failed" ? "#FF4D4D"
                    : edge.status === "validated_only" ? "#4DA6FF"
                    : "#4CC46A";
                const dash = edge.dryRun ? 'stroke-dasharray="5 4"' : '';
                return `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${color}" stroke-width="2" ${dash} marker-end="url(#bg_arrow)" opacity="0.9" />`;
            }).join('');

            const nodeSvg = nodes.map((n) => {
                const p = pos[n.id];
                if (!p) return '';
                const color = String(n.presence?.color || '').trim().toLowerCase();
                const fill = color === 'green' ? "#183923" : color === 'blue' ? "#132d4f" : color === 'red' ? "#4a1717" : "#343b48";
                const stroke = color === 'green' ? "#4CC46A" : color === 'blue' ? "#4DA6FF" : color === 'red' ? "#FF6262" : "#94a3b8";
                const agentText = n.agents.length ? ` | ${n.agents.slice(0, 2).join(",")}` : "";
                const px = Number(p.x.toFixed(1));
                const py = Number(p.y.toFixed(1));
                return `
                    <g>
                        <circle cx="${p.x}" cy="${p.y}" r="22" fill="${fill}" stroke="${stroke}" stroke-width="2" onclick="selectBossGatePresence('node', '${escapeHtml(n.id)}', ${px}, ${py})" style="cursor:pointer;" />
                        <text x="${p.x}" y="${p.y - 30}" text-anchor="middle" fill="#e6ddcb" font-size="12">${escapeHtml(n.label)}</text>
                        <text x="${p.x}" y="${p.y + 42}" text-anchor="middle" fill="#a9b1c1" font-size="11">${escapeHtml(n.type + agentText)}</text>
                    </g>
                `;
            }).join('');

            const agentSvg = agentPresences.map((presence, idx) => {
                const anchor = pos[String(presence.current_node_id || presence.origin_node_id || '').trim()];
                if (!anchor) return '';
                const offsetAngle = (idx % 6) * (Math.PI / 3);
                const ax = anchor.x + 34 * Math.cos(offsetAngle);
                const ay = anchor.y + 34 * Math.sin(offsetAngle);
                const stroke = presence.color === 'green' ? "#4CC46A" : presence.color === 'blue' ? "#4DA6FF" : presence.color === 'red' ? "#FF6262" : "#94a3b8";
                return `
                    <g>
                        <circle cx="${ax}" cy="${ay}" r="9" fill="#0b121d" stroke="${stroke}" stroke-width="2" onclick="selectBossGatePresence('agent', '${escapeHtml(presence.agent_name || presence.agent_id)}', ${Number(ax.toFixed(1))}, ${Number(ay.toFixed(1))})" style="cursor:pointer;" />
                    </g>
                `;
            }).join('');

            const edgeList = edgeItems.slice(-10).reverse().map((e) => {
                const from = nodeById[e.from] ? nodeById[e.from].label : e.from;
                const to = nodeById[e.to] ? nodeById[e.to].label : e.to;
                const when = e.timestamp > 0 ? new Date(e.timestamp * 1000).toLocaleString() : "unknown-time";
                return `<div class="topology-edge-item">${escapeHtml(when)} | ${escapeHtml(from)} -> ${escapeHtml(to)} | ${escapeHtml(e.status)}${e.dryRun ? " (dry-run)" : ""}</div>`;
            }).join('');

            root.innerHTML = `
                <div class="bossgate-presence-layout">
                    <div id="bossgate_presence_card">${renderBossGatePresenceCard(bossGatePresenceState.selected || nodePresences[0] || agentPresences[0] || null)}</div>
                    <div class="bossgate-presence-stage">
                        <svg class="topology-graph" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet">
                            <defs>
                                <marker id="bg_arrow" markerWidth="8" markerHeight="8" refX="6" refY="3.5" orient="auto">
                                    <polygon points="0 0, 7 3.5, 0 7" fill="#D4A857"></polygon>
                                </marker>
                            </defs>
                            ${edgeSvg}
                            ${nodeSvg}
                            ${agentSvg}
                        </svg>
                        <div id="bossgate_topology_overlay">${renderBossGateRadialMenu(bossGatePresenceState.selected || nodePresences[0] || agentPresences[0] || null, cx, cy)}</div>
                    </div>
                    <div class="topology-legend">Green edge: posted transfer. Blue dashed edge: dry-run validation. Red edge: failed transfer. Green markers: your forge. Blue markers: trade-linked. Red markers: revealed unknowns. Grey markers: unresolved beacons.</div>
                    <div class="topology-edge-list">${edgeList || '<div class="topology-empty">No recent transfer edges.</div>'}</div>
                </div>
            `;
        }

        function renderSoundEvents() {
            const root = document.getElementById('sound_events');
            if (!root) return;
            root.textContent = JSON.stringify({ events: soundEvents, scheme: soundScheme }, null, 2);
        }

        function iconAssetPath(fileName) {
            return '/api/assets/icons/' + encodeURIComponent(String(fileName || '').trim());
        }

        function applyAssetIcons() {
            const navIconMap = {
                view_status: 'BossForgeOS.png',
                view_snapshot: 'BossForgeOS.png',
                view_os_state: 'BossForgeOS.png',
                view_commands: 'BossGate.png',
                view_manual: 'BossGate.png',
                view_seal: 'runebus.svg',
                view_events: 'runebus.svg',
                view_bus: 'runebus.svg',
                view_cicd: 'AgentForge.png',
                view_onboarding: 'RuneVoiceOS.png',
                view_scheduler: 'AgentForge.png',
                view_chat: 'RuneVoiceOS.png',
                view_maker: 'AgentForge.png',
                view_bossgate_map: 'BossGate.png',
                view_iconforge: 'IconForge.png',
                view_discovery: 'BossGate.png',
                view_security: 'bossgate.svg',
                view_sounds: 'Soundforge.png',
                view_diagnostics: 'BossForgeOS.png',
            };
            const panelIconMap = {
                view_status: 'BossForgeOS.png',
                view_snapshot: 'BossForgeOS.png',
                view_os_state: 'BossForgeOS.png',
                view_commands: 'BossGate.png',
                view_manual: 'BossGate.png',
                view_seal: 'runebus.svg',
                view_events: 'runebus.svg',
                view_bus: 'runebus.svg',
                view_chat: 'RuneVoiceOS.png',
                view_diagnostics: 'BossForgeOS.png',
                view_sounds: 'Soundforge.png',
                view_maker: 'AgentForge.png',
                view_bossgate_map: 'BossGate.png',
                view_iconforge: 'IconForge.png',
                view_security: 'bossgate.svg',
                view_onboarding: 'RuneVoiceOS.png',
                view_scheduler: 'AgentForge.png',
                view_cicd: 'AgentForge.png',
            };

            for (const [viewId, fileName] of Object.entries(navIconMap)) {
                const btn = document.querySelector(`.nav-btn[data-view="${viewId}"]`);
                if (!btn) continue;
                btn.style.setProperty('--nav-icon', `url("${iconAssetPath(fileName)}")`);
            }

            for (const [sectionId, fileName] of Object.entries(panelIconMap)) {
                const section = document.getElementById(sectionId);
                if (!section) continue;
                const h2 = section.querySelector('h2');
                if (!h2) continue;
                h2.classList.add('panel-heading');
                let icon = h2.querySelector('.panel-icon');
                if (!icon) {
                    icon = document.createElement('img');
                    icon.className = 'panel-icon';
                    icon.alt = '';
                    h2.prepend(icon);
                }
                icon.src = iconAssetPath(fileName);
            }
        }

        async function fetchSoundEvents() {
            const data = await fetchJsonWithTimeout('/api/soundforge/list_schemes');
            const cfg = await fetchJsonWithTimeout('/api/soundforge/config');
            if (data && data.ok && cfg && cfg.ok) {
                soundEvents = [];
                soundScheme = {
                    available_schemes: data.schemes || [],
                    active_config: cfg.config || {},
                };
                setSoundSchemeStatus('SoundForge schemes and active config loaded.');
            } else {
                setSoundSchemeStatus('Unable to load sound schemes.');
            }
            renderSoundEvents();
        }

        function switchView(viewId) {
            beginBusy('Loading tab...');
            currentView = viewId;
            if (busLiveTimer) {
                clearInterval(busLiveTimer);
                busLiveTimer = null;
            }
            document.querySelectorAll('.view-panel').forEach((el) => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach((el) => el.classList.remove('active'));
            const panel = document.getElementById(viewId);
            if (panel) panel.classList.add('active');
            const btn = document.querySelector(`.nav-btn[data-view="${viewId}"]`);
            if (btn) btn.classList.add('active');
            syncPinControls();
            if (viewId === 'view_diagnostics') refreshDiagnostics();
            if (viewId === 'view_sounds') fetchSoundEvents();
            if (viewId === 'view_discovery') refreshDiscoveryMap();
            if (viewId === 'view_bossgate_map') refreshBossGateMap(true);
            if (viewId === 'view_bossgate_access') refreshBossGateAccess();
            if (viewId === 'view_iconforge') {
                refreshIconForgeOps();
                if (!iconForgeVisited) {
                    iconForgeVisited = true;
                    showIconForgeSchematics();
                }
            }
            if (viewId === 'view_os_state') refreshOsStatePanel();
            if (viewId === 'view_onboarding') refreshOnboardingStatus();
            if (viewId === 'view_scheduler') refreshSchedulerStatus();
            if (viewId === 'view_cicd') refreshCicdStatus();
            if (viewId === 'view_bus') {
                refreshBusInspector();
                const live = !!document.getElementById('bus_live')?.checked;
                if (live) {
                    busLiveTimer = setInterval(() => {
                        if (currentView === 'view_bus') refreshBusInspector();
                    }, 2000);
                }
            }
            setTimeout(endBusy, 180);
        }

        function applyStandaloneProductMode(mode) {
            const cfg = PRODUCT_MODE_CONFIG[mode];
            if (!cfg) return false;

            const shellTitle = document.getElementById('shell_title');
            const shellSubtitle = document.getElementById('shell_subtitle');
            const hallTitle = document.getElementById('hall_title');
            const hallSubtitle = document.getElementById('hall_subtitle');
            const pinRow = document.getElementById('hall_pin_row');
            const anvilBtn = document.getElementById('anvil_launch_btn');
            const anvilStatus = document.getElementById('anvil_status');

            if (shellTitle) shellTitle.textContent = cfg.title;
            if (shellSubtitle) shellSubtitle.textContent = cfg.subtitle;
            if (hallTitle) hallTitle.textContent = cfg.hallTitle;
            if (hallSubtitle) hallSubtitle.textContent = cfg.hallSubtitle;
            if (pinRow) pinRow.style.display = 'none';
            if (anvilBtn) anvilBtn.style.display = 'none';
            if (anvilStatus) anvilStatus.style.display = 'none';
            document.title = cfg.hallTitle;

            const allowed = new Set(cfg.allowedViews || []);
            document.querySelectorAll('.nav-btn').forEach((btn) => {
                const view = String(btn.getAttribute('data-view') || '');
                btn.style.display = allowed.has(view) ? '' : 'none';
            });

            document.querySelectorAll('.group-label').forEach((label) => {
                let sib = label.nextElementSibling;
                let visibleCount = 0;
                while (sib && !sib.classList.contains('group-label')) {
                    if (sib.classList.contains('nav-btn') && sib.style.display !== 'none') visibleCount += 1;
                    sib = sib.nextElementSibling;
                }
                label.style.display = visibleCount ? '' : 'none';
            });

            switchView(cfg.defaultView);
            return true;
        }

        function applyUrlLaunchContext() {
            const params = new URLSearchParams(window.location.search || '');
            const mode = String(params.get('mode') || '').trim().toLowerCase();
            const modeApplied = applyStandaloneProductMode(mode);
            const afIcon = String(params.get('agentforge_icon') || '').trim().toLowerCase();
            const afTarget = String(params.get('agentforge_target') || '').trim().toLowerCase();
            const afAgentName = String(params.get('agent_name') || '').trim();
            if (afIcon === '1' || afIcon === 'true' || afIcon === 'yes') {
                iconForgeAgentContext = {
                    active: true,
                    source: (afTarget === 'wizard' || afTarget === 'advanced') ? afTarget : 'advanced',
                    agentName: afAgentName,
                };
            } else if (modeApplied) {
                iconForgeAgentContext = { active: false, source: '', agentName: '' };
            }
            applyIconForgeAgentContextUI();
            const requestedView = (params.get('view') || '').trim();
            if (requestedView && document.getElementById(requestedView)) {
                switchView(requestedView);
            } else if (!modeApplied && currentView !== 'view_status') {
                switchView('view_status');
            }

            const openIcon = (params.get('open_icon') || '').trim();
            if (!openIcon) return;

            if (currentView !== 'view_iconforge') {
                switchView('view_iconforge');
            }
            showIconForgeEditor('Explorer selection');

            const iconPathInput = document.getElementById('iconforge_icon_path');
            if (iconPathInput) {
                iconPathInput.value = openIcon;
            }

            const baseName = openIcon.split(/[\\/]/).pop() || '';
            const iconStem = baseName.replace(/\\.[^.]+$/, '').trim();
            const studioName = document.getElementById('icon_studio_name');
            if (studioName && iconStem) {
                studioName.value = iconStem;
            }

            setIconStudioStatus('Explorer selection loaded: ' + openIcon);
        }

        async function refreshOnboardingStatus() {
            const data = await fetchJsonWithTimeout('/api/onboarding/status');
            const root = document.getElementById('onboarding_status');
            if (!root) return;
            root.textContent = JSON.stringify(data, null, 2);
        }

        async function runOnboardingStep(step) {
            const root = document.getElementById('onboarding_status');
            if (root) root.textContent = 'Running onboarding step...';
            const res = await fetch('/api/onboarding', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ step })
            });
            const data = await res.json();
            if (root) root.textContent = JSON.stringify(data, null, 2);
            await refreshOnboardingStatus();
        }

        async function refreshSchedulerStatus() {
            const data = await fetchJsonWithTimeout('/api/scheduler');
            const root = document.getElementById('scheduler_status');
            if (!root) return;
            root.textContent = JSON.stringify(data, null, 2);
        }

        async function addSchedulerJob() {
            const label = (document.getElementById('scheduler_label').value || '').trim();
            const command = (document.getElementById('scheduler_command').value || '').trim();
            const interval = Number(document.getElementById('scheduler_interval').value || 300);
            const res = await fetch('/api/scheduler', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'add', label, command, interval_seconds: interval })
            });
            const data = await res.json();
            document.getElementById('scheduler_status').textContent = JSON.stringify(data, null, 2);
            await refreshSchedulerStatus();
        }

        async function removeSchedulerJob() {
            const id = (document.getElementById('scheduler_remove_id').value || '').trim();
            if (!id) {
                alert('job id is required');
                return;
            }
            const res = await fetch('/api/scheduler', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'remove', id })
            });
            const data = await res.json();
            document.getElementById('scheduler_status').textContent = JSON.stringify(data, null, 2);
            await refreshSchedulerStatus();
        }

        async function runSchedulerJobNow() {
            const id = (document.getElementById('scheduler_run_id').value || '').trim();
            if (!id) {
                alert('job id is required');
                return;
            }
            const res = await fetch('/api/scheduler', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'run_now', id })
            });
            const data = await res.json();
            document.getElementById('scheduler_status').textContent = JSON.stringify(data, null, 2);
            await refreshSchedulerStatus();
        }

        async function refreshCicdStatus() {
            const data = await fetchJsonWithTimeout('/api/cicd');
            const root = document.getElementById('cicd_status');
            if (!root) return;
            root.textContent = JSON.stringify(data, null, 2);
        }

        async function runCicdPipeline() {
            const suite = (document.getElementById('cicd_suite').value || 'quick').trim();
            const root = document.getElementById('cicd_status');
            if (root) root.textContent = 'Running CI/CD pipeline...';
            const res = await fetch('/api/cicd', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: 'run', suite })
            });
            const data = await res.json();
            if (root) root.textContent = JSON.stringify(data, null, 2);
            await refreshCicdStatus();
        }

        async function fetchJsonWithTimeout(url, timeoutMs = 4000) {
            const ctl = new AbortController();
            const timer = setTimeout(() => ctl.abort(), timeoutMs);
            beginBusy('Fetching data...');
            try {
                const res = await fetch(url, { signal: ctl.signal });
                if (!res.ok) return { ok: false, error: 'HTTP ' + res.status };
                return await res.json();
            } catch (err) {
                return { ok: false, error: String(err) };
            } finally {
                clearTimeout(timer);
                endBusy();
            }
        }

        function syncPinControls() {
            const note = document.getElementById('pin_note');
            const toggle = document.getElementById('pin_toggle');
            if (!note || !toggle) return;
            if (!pinnedOverlayViewId) {
                note.textContent = 'No desktop pin active';
                toggle.textContent = 'Pin Current View';
                return;
            }
            const pinnedNav = document.querySelector(`.nav-btn[data-view="${pinnedOverlayViewId}"]`);
            const pinnedTitle = pinnedNav ? pinnedNav.textContent.trim() : pinnedOverlayViewId;
            note.textContent = 'Pinned (always-on-top desktop): ' + pinnedTitle;
            toggle.textContent = pinnedOverlayViewId === currentView ? 'Unpin Current View' : 'Pin Current View';
        }

        async function refreshPinState() {
            const data = await fetchJsonWithTimeout('/api/pin/state');
            pinnedOverlayViewId = (data && data.running) ? (data.view || '') : '';
            syncPinControls();
        }

        async function launchPinnedOverlay(viewId) {
            const res = await fetch('/api/pin/launch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ view: viewId, alpha: 0.95 })
            });
            const data = await res.json();
            if (!data.ok) {
                alert(data.message || 'Failed to pin view');
                return;
            }
            pinnedOverlayViewId = data.view || '';
            syncPinControls();
        }

        async function clearPinnedView() {
            await fetch('/api/pin/close', { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            pinnedOverlayViewId = '';
            syncPinControls();
        }

        async function togglePinCurrentView() {
            if (pinnedOverlayViewId === currentView) {
                await clearPinnedView();
                return;
            }
            await launchPinnedOverlay(currentView);
        }

        async function sendCmd(target, command, args) {
            const res = await fetch('/api/command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target, command, args })
            });
            const data = await res.json();
            document.getElementById('toast').textContent = data.ok ? ('Command queued: ' + command) : ('Command failed: ' + (data.message || 'unknown error'));
            refresh();
        }

        function bossGateCurrentUser() {
            const input = document.getElementById('bossgate_current_user');
            const user = String(input?.value || localStorage.getItem('bossgate_current_user') || 'bossforge-owner').trim() || 'bossforge-owner';
            localStorage.setItem('bossgate_current_user', user);
            if (input) input.value = user;
            return user;
        }

        function csvValues(id) {
            return String(document.getElementById(id)?.value || '').split(',').map((item) => item.trim()).filter(Boolean);
        }

        async function refreshBossGateAccess() {
            const user = bossGateCurrentUser();
            const data = await fetchJsonWithTimeout('/api/bossgate/access/capabilities?user_id=' + encodeURIComponent(user));
            const policy = await fetchJsonWithTimeout('/api/bossgate/access/policy');
            const permissions = new Set(Array.isArray(data?.permissions) ? data.permissions : []);
            const panels = data?.panels || {};
            document.querySelectorAll('[data-bossgate-permission]').forEach((el) => {
                el.style.display = permissions.has(el.dataset.bossgatePermission) ? '' : 'none';
            });
            document.querySelectorAll('[data-bossgate-panel]').forEach((el) => {
                el.style.display = panels[el.dataset.bossgatePanel] ? '' : 'none';
            });
            const summary = document.getElementById('bossgate_access_summary');
            if (summary) summary.textContent = JSON.stringify({ ...data, policy: policy?.policy || {} }, null, 2);
            const commerce = document.getElementById('bossgate_commerce_summary');
            if (commerce) commerce.textContent = JSON.stringify({ enabled: !!panels.commerce, permissions: [...permissions].filter((item) => item.includes('license') || item.includes('usage') || item.includes('commerce')) }, null, 2);
            const support = document.getElementById('bossgate_support_summary');
            if (support) support.textContent = JSON.stringify({ enabled: !!panels.support, permissions: [...permissions].filter((item) => item.includes('remote_debug') || item.includes('support')) }, null, 2);
        }

        async function dispatchBossGateOperator(command) {
            const base = { operator_id: bossGateCurrentUser(), scope_id: 'control-hall', actor_type: 'human' };
            if (command === 'bossgate_package_agent') {
                Object.assign(base, { name: document.getElementById('bossgate_package_agent_name').value.trim(), target_system_id: document.getElementById('bossgate_package_target').value.trim() });
            } else if (command === 'bossgate_transfer_agent') {
                Object.assign(base, { package_file: document.getElementById('bossgate_transfer_file').value.trim(), destination: document.getElementById('bossgate_transfer_destination').value.trim(), dry_run: true });
            } else if (command === 'bossgate_install_agent') {
                Object.assign(base, { package_file: document.getElementById('bossgate_install_file').value.trim() });
            }
            await sendCmd('bossgate', command, base);
        }

        async function assignBossGateRoles() {
            const userId = document.getElementById('bossgate_assign_user').value.trim();
            const res = await fetch('/api/bossgate/access/users/' + encodeURIComponent(userId) + '/roles', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ acting_user: bossGateCurrentUser(), roles: csvValues('bossgate_assign_roles') }) });
            document.getElementById('toast').textContent = JSON.stringify(await res.json());
            await refreshBossGateAccess();
        }

        async function saveBossGateCustomRole() {
            const res = await fetch('/api/bossgate/access/roles', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ acting_user: bossGateCurrentUser(), role_name: document.getElementById('bossgate_custom_role').value.trim(), permissions: csvValues('bossgate_custom_permissions') }) });
            document.getElementById('toast').textContent = JSON.stringify(await res.json());
            await refreshBossGateAccess();
        }

        function refreshTargetDropdown(agents) {
            const target = document.getElementById('target');
            if (!target) return;
            const current = target.value;
            target.innerHTML = '';
            const keys = Object.keys(agents || {});
            for (const key of keys) {
                const op = document.createElement('option');
                op.value = key;
                op.textContent = key;
                target.appendChild(op);
            }
            if (current && keys.includes(current)) target.value = current;
        }

        async function refreshChatEndpoints() {
            const data = await fetchJsonWithTimeout('/api/model/endpoints');
            const endpoints = (data && data.endpoints && typeof data.endpoints === 'object') ? Object.keys(data.endpoints) : [];
            const chat = document.getElementById('chat_endpoint');
            const maker = document.getElementById('maker_endpoint');
            const wizard = document.getElementById('wizard_endpoint');
            const override = document.getElementById('maker_override_endpoint');
            if (chat) {
                const selected = chat.value;
                chat.innerHTML = endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) chat.value = selected;
            }
            if (maker) {
                const selected = maker.value;
                maker.innerHTML = endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) maker.value = selected;
            }
            if (wizard) {
                const selected = wizard.value;
                wizard.innerHTML = endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) wizard.value = selected;
                else if (!selected && endpoints.length) wizard.value = endpoints[0];
            }
            if (override) {
                const selected = override.value;
                override.innerHTML = '<option value="">(agent default)</option>' + endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) override.value = selected;
            }
        }

        function selectedAdvancedSkills() {
            const skillIds = [
                'skill_command',
                'skill_bossgate_travel_control',
                'skill_runtime_observation',
                'skill_task_queue_management',
                'skill_web_search',
                'skill_policy_planning',
                'skill_memory_sync',
                'skill_incident_triage',
                'skill_code_review',
                'skill_ui_design',
                'skill_art_direction',
                'skill_documentation_crafting',
                'skill_test_orchestration',
                'skill_security_audit',
                'skill_performance_tuning',
                'skill_data_analysis',
                'skill_workflow_automation',
                'skill_customer_support',
                'skill_integration_mapping',
                'skill_api_composition',
            ];
            const skills = [];
            for (const id of skillIds) {
                const el = document.getElementById(id);
                if (!el || !el.checked) continue;
                skills.push(id.replace('skill_', ''));
            }
            return skills;
        }

        function selectedAdvancedSigils() {
            const sigilIds = [
                'sigil_sigil_transporter',
                'sigil_prime_overwatch',
                'sigil_sigil_bind',
                'sigil_sigil_trace',
                'sigil_sigil_harmony',
                'sigil_prime_foresight',
                'sigil_prime_bastion',
                'sigil_sigil_palette',
                'sigil_sigil_resonance',
                'sigil_sigil_flux',
                'sigil_sigil_anchor',
                'sigil_sigil_lens',
                'sigil_sigil_weave',
                'sigil_sigil_echo',
                'sigil_sigil_guard',
                'sigil_sigil_spark',
                'sigil_sigil_patch',
                'sigil_sigil_scribe',
                'sigil_sigil_orbit',
                'sigil_sigil_shield',
            ];
            const sigils = [];
            for (const id of sigilIds) {
                const el = document.getElementById(id);
                if (!el || !el.checked) continue;
                sigils.push(id.replace('sigil_', ''));
            }
            return sigils;
        }

        function parseCsvTags(raw) {
            return String(raw || '')
                .split(',')
                .map((item) => item.trim().toLowerCase())
                .filter((item) => !!item);
        }

        function setIconStatus(statusId, message, isError = false) {
            const root = document.getElementById(statusId);
            if (!root) return;
            root.textContent = String(message || '');
            root.style.color = isError ? '#f17171' : '#A9B1C1';
        }

        async function uploadAgentForgeIcon(file, iconNameHint) {
            if (!file) return { ok: false, message: 'no file provided' };
            const form = new FormData();
            form.append('icon', file);
            form.append('icon_name', String(iconNameHint || '').trim());
            const res = await fetch('/api/agentforge/icon/upload', { method: 'POST', body: form });
            return await res.json();
        }

        async function createAgentForgeIcon(iconNameHint, label, background, foreground) {
            const payload = {
                icon_name: String(iconNameHint || '').trim(),
                label: String(label || '').trim(),
                background: String(background || '').trim(),
                foreground: String(foreground || '').trim(),
            };
            const res = await fetch('/api/agentforge/icon/create', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            return await res.json();
        }

        function toggleWizardIconSource() {
            const mode = (document.getElementById('wizard_icon_mode')?.value || 'none').trim();
            const uploadRow = document.getElementById('wizard_icon_upload_row');
            const forgeRow = document.getElementById('wizard_iconforge_row');
            if (uploadRow) uploadRow.style.display = mode === 'upload' ? 'flex' : 'none';
            if (forgeRow) forgeRow.style.display = mode === 'iconforge' ? 'flex' : 'none';
            if (mode === 'none') {
                const path = document.getElementById('wizard_icon_path');
                if (path) path.value = '';
                setIconStatus('wizard_icon_status', 'Using default icon.');
            }
        }

        function clearWizardIconSelection() {
            const path = document.getElementById('wizard_icon_path');
            if (path) path.value = '';
            const mode = document.getElementById('wizard_icon_mode');
            if (mode) mode.value = 'none';
            const uploadName = document.getElementById('wizard_icon_upload_name');
            if (uploadName) uploadName.textContent = 'No file selected';
            toggleWizardIconSource();
        }

        function triggerWizardIconUpload() {
            const file = document.getElementById('wizard_icon_upload_file');
            if (file) file.click();
        }

        async function handleWizardIconUpload(event) {
            const file = event?.target?.files?.[0];
            if (!file) return;
            const uploadName = document.getElementById('wizard_icon_upload_name');
            if (uploadName) uploadName.textContent = file.name;
            setIconStatus('wizard_icon_status', 'Uploading icon...');
            const iconNameHint = (document.getElementById('wizard_name')?.value || 'wizard_agent').trim();
            const data = await uploadAgentForgeIcon(file, iconNameHint);
            if (data && data.ok) {
                const path = document.getElementById('wizard_icon_path');
                if (path) path.value = String(data.icon || '');
                setIconStatus('wizard_icon_status', 'Custom icon ready: ' + String(data.icon || ''));
            } else {
                setIconStatus('wizard_icon_status', 'Icon upload failed: ' + String(data?.message || 'unknown error'), true);
            }
        }

        async function createWizardIconForge() {
            setIconStatus('wizard_icon_status', 'Creating icon via IconForge...');
            const iconNameHint = (document.getElementById('wizard_name')?.value || 'wizard_agent').trim();
            const label = document.getElementById('wizard_icon_label')?.value || 'AG';
            const bg = document.getElementById('wizard_icon_bg')?.value || '#1d3557';
            const fg = document.getElementById('wizard_icon_fg')?.value || '#f1faee';
            const data = await createAgentForgeIcon(iconNameHint, label, bg, fg);
            if (data && data.ok) {
                const path = document.getElementById('wizard_icon_path');
                if (path) path.value = String(data.icon || '');
                setIconStatus('wizard_icon_status', 'Custom icon ready: ' + String(data.icon || ''));
            } else {
                setIconStatus('wizard_icon_status', 'IconForge create failed: ' + String(data?.message || 'unknown error'), true);
            }
        }

        function toggleMakerIconSource() {
            const mode = (document.getElementById('maker_icon_mode')?.value || 'none').trim();
            const uploadRow = document.getElementById('maker_icon_upload_row');
            const forgeRow = document.getElementById('maker_iconforge_row');
            if (uploadRow) uploadRow.style.display = mode === 'upload' ? 'flex' : 'none';
            if (forgeRow) forgeRow.style.display = mode === 'iconforge' ? 'flex' : 'none';
            if (mode === 'none') {
                const path = document.getElementById('maker_icon_path');
                if (path) path.value = '';
                setIconStatus('maker_icon_status', 'Using default icon.');
            }
        }

        function clearMakerIconSelection() {
            const path = document.getElementById('maker_icon_path');
            if (path) path.value = '';
            const mode = document.getElementById('maker_icon_mode');
            if (mode) mode.value = 'none';
            const uploadName = document.getElementById('maker_icon_upload_name');
            if (uploadName) uploadName.textContent = 'No file selected';
            toggleMakerIconSource();
        }

        function triggerMakerIconUpload() {
            const file = document.getElementById('maker_icon_upload_file');
            if (file) file.click();
        }

        async function handleMakerIconUpload(event) {
            const file = event?.target?.files?.[0];
            if (!file) return;
            const uploadName = document.getElementById('maker_icon_upload_name');
            if (uploadName) uploadName.textContent = file.name;
            setIconStatus('maker_icon_status', 'Uploading icon...');
            const iconNameHint = (document.getElementById('maker_name')?.value || 'advanced_agent').trim();
            const data = await uploadAgentForgeIcon(file, iconNameHint);
            if (data && data.ok) {
                const path = document.getElementById('maker_icon_path');
                if (path) path.value = String(data.icon || '');
                setIconStatus('maker_icon_status', 'Custom icon ready: ' + String(data.icon || ''));
            } else {
                setIconStatus('maker_icon_status', 'Icon upload failed: ' + String(data?.message || 'unknown error'), true);
            }
        }

        async function createMakerIconForge() {
            setIconStatus('maker_icon_status', 'Creating icon via IconForge...');
            const iconNameHint = (document.getElementById('maker_name')?.value || 'advanced_agent').trim();
            const label = document.getElementById('maker_icon_label')?.value || 'AG';
            const bg = document.getElementById('maker_icon_bg')?.value || '#1d3557';
            const fg = document.getElementById('maker_icon_fg')?.value || '#f1faee';
            const data = await createAgentForgeIcon(iconNameHint, label, bg, fg);
            if (data && data.ok) {
                const path = document.getElementById('maker_icon_path');
                if (path) path.value = String(data.icon || '');
                setIconStatus('maker_icon_status', 'Custom icon ready: ' + String(data.icon || ''));
            } else {
                setIconStatus('maker_icon_status', 'IconForge create failed: ' + String(data?.message || 'unknown error'), true);
            }
        }

        function setIconStudioStatus(message, isError = false) {
            const root = document.getElementById('icon_studio_status');
            if (!root) return;
            root.textContent = String(message || '');
            root.style.color = isError ? '#f17171' : '#A9B1C1';
        }

        function applyIconForgeAgentContextUI() {
            const row = document.getElementById('icon_studio_agentforge_row');
            const hint = document.getElementById('icon_studio_agentforge_hint');
            const target = document.getElementById('icon_studio_target');
            if (row) row.style.display = iconForgeAgentContext.active ? 'flex' : 'none';
            if (hint) {
                hint.style.display = iconForgeAgentContext.active ? 'block' : 'none';
                if (iconForgeAgentContext.active) {
                    const src = iconForgeAgentContext.source || 'advanced';
                    const agent = iconForgeAgentContext.agentName ? (' (' + iconForgeAgentContext.agentName + ')') : '';
                    hint.textContent = 'AgentForge session active: target=' + src + agent + '.';
                }
            }
            if (target) {
                if (!iconForgeAgentContext.active) {
                    target.value = 'standalone';
                } else if (iconForgeAgentContext.source === 'wizard' || iconForgeAgentContext.source === 'advanced') {
                    target.value = iconForgeAgentContext.source;
                }
            }
        }

        function openIconForgeFromAgentForge(source) {
            const src = (source === 'wizard' || source === 'advanced') ? source : 'advanced';
            const name = src === 'wizard'
                ? String(document.getElementById('wizard_name')?.value || '').trim()
                : String(document.getElementById('maker_name')?.value || '').trim();
            iconForgeAgentContext = { active: true, source: src, agentName: name };
            const studioName = document.getElementById('icon_studio_name');
            if (studioName && name) studioName.value = name;
            applyIconForgeAgentContextUI();
            switchView('view_iconforge');
            showIconForgeEditor();
            setIconStudioStatus('AgentForge icon session opened (' + src + ').');
        }

        function iconForgeSafeText(value, fallback = '') {
            const raw = String(value || '').trim();
            return raw || fallback;
        }

        function iconForgeInferStem(pathLike, fallback = 'iconforge_item') {
            const raw = String(pathLike || '').trim();
            if (!raw) return fallback;
            const base = raw.split(/[\\/]/).pop() || raw;
            const stem = base.replace(/\\.[^.]+$/, '').trim();
            return stem || fallback;
        }

        function iconForgeBuildPreviewUrl(pathLike) {
            const raw = String(pathLike || '').trim();
            if (!raw) return '';
            if (raw.startsWith('data:image/')) return raw;
            if (/^https?:\\/\\//i.test(raw)) return raw;
            return '/api/iconforge/preview?path=' + encodeURIComponent(raw);
        }

        function iconForgeLoadSectionCollapseState() {
            try {
                const raw = localStorage.getItem('bossforge.iconforge.sections.collapsed.v1');
                if (!raw) {
                    iconForgeSectionCollapseState = {};
                    return;
                }
                const parsed = JSON.parse(raw);
                iconForgeSectionCollapseState = (parsed && typeof parsed === 'object') ? parsed : {};
            } catch {
                iconForgeSectionCollapseState = {};
            }
        }

        function iconForgeSaveSectionCollapseState() {
            try {
                localStorage.setItem('bossforge.iconforge.sections.collapsed.v1', JSON.stringify(iconForgeSectionCollapseState || {}));
            } catch {
                // Ignore storage failures.
            }
        }

        function iconForgeSectionIsCollapsed(sectionKey) {
            return iconForgeSectionCollapseState && iconForgeSectionCollapseState[String(sectionKey)] === true;
        }

        function iconForgeToggleSection(sectionKey) {
            const key = String(sectionKey || '').trim();
            if (!key) return;
            const next = !iconForgeSectionIsCollapsed(key);
            iconForgeSectionCollapseState[key] = next;
            iconForgeSaveSectionCollapseState();
            renderIconForgeSchematics();
        }

        function collectIconForgeSchematics() {
            const items = [];
            const wizardIcon = String(document.getElementById('wizard_icon_path')?.value || '').trim();
            const wizardName = String(document.getElementById('wizard_name')?.value || '').trim();
            items.push({
                id: 'agentforge-wizard',
                title: 'AgentForge Wizard',
                where: 'wizard creation profile',
                targetType: 'agentforge',
                target: 'wizard icon slot',
                icon: wizardIcon,
                source: 'wizard',
                agentName: wizardName,
            });

            const makerIcon = String(document.getElementById('maker_icon_path')?.value || '').trim();
            const makerName = String(document.getElementById('maker_name')?.value || '').trim();
            items.push({
                id: 'agentforge-advanced',
                title: 'AgentForge Advanced',
                where: 'advanced agent profile',
                targetType: 'agentforge',
                target: 'advanced icon slot',
                icon: makerIcon,
                source: 'advanced',
                agentName: makerName,
            });

            const windowsTemplates = [
                {
                    id: 'windows-folder-template',
                    title: 'Windows Folder Icon',
                    where: 'folder shell icon',
                    targetType: 'folder',
                    target: 'C:/Path/To/Folder',
                    icon: '',
                },
                {
                    id: 'windows-shortcut-template',
                    title: 'Windows Shortcut Icon',
                    where: 'shortcut (.lnk) icon',
                    targetType: 'shortcut',
                    target: 'C:/Path/To/AppShortcut.lnk',
                    icon: '',
                },
                {
                    id: 'windows-file-extension-template',
                    title: 'Windows File Extension Icon',
                    where: 'extension class icon',
                    targetType: 'file_extension',
                    target: '.txt',
                    icon: '',
                },
                {
                    id: 'windows-application-template',
                    title: 'Windows Application Icon',
                    where: 'application registration icon',
                    targetType: 'application',
                    target: 'notepad.exe',
                    icon: '',
                },
                {
                    id: 'windows-drive-template',
                    title: 'Windows Drive Icon',
                    where: 'drive letter shell icon',
                    targetType: 'drive',
                    target: 'D',
                    icon: '',
                },
            ];
            windowsTemplates.forEach((entry) => {
                items.push({ ...entry, source: 'windows-template' });
            });

            const backupItems = (iconForgeBackupsCache && typeof iconForgeBackupsCache === 'object') ? iconForgeBackupsCache : {};
            Object.entries(backupItems).forEach(([key, entry], index) => {
                if (!entry || typeof entry !== 'object') return;
                const targetType = String(entry.target_type || 'unknown').trim() || 'unknown';
                const target = String(entry.target || key).trim() || key;
                const icon = String(entry.icon || '').trim();
                items.push({
                    id: 'backup-' + String(index),
                    title: 'Windows Override: ' + targetType,
                    where: 'windows shell icon override',
                    targetType,
                    target,
                    icon,
                    backupKey: key,
                    source: 'windows',
                });
            });

            return items;
        }

        function renderIconForgeSchematics() {
            iconForgeSchematics = collectIconForgeSchematics();
            const statsRoot = document.getElementById('iconforge_schematics_stats');
            const gridRoot = document.getElementById('iconforge_schematics_grid');
            if (!statsRoot || !gridRoot) return;

            const total = iconForgeSchematics.length;
            const withIcon = iconForgeSchematics.filter((item) => String(item.icon || '').trim()).length;
            const withPreview = iconForgeSchematics.filter((item) => String(iconForgeBuildPreviewUrl(item.icon) || '').trim()).length;
            statsRoot.textContent = 'Targets mapped: ' + String(total) + ' | with icon path: ' + String(withIcon) + ' | previewable: ' + String(withPreview) + ' | click a tile to edit.';

            if (!total) {
                gridRoot.innerHTML = '<div class="iconforge-schematic-card"><h4>No icon targets found</h4><div class="iconforge-schematic-meta">Create or apply icon operations to populate the map.</div></div>';
                return;
            }

            const sectionConfig = [
                { key: 'agentforge', label: 'AgentForge Icon Targets' },
                { key: 'windows-template', label: 'Windows Icon Templates' },
                { key: 'windows', label: 'Active Windows Overrides' },
            ];

            const grouped = {
                agentforge: [],
                'windows-template': [],
                windows: [],
                other: [],
            };
            iconForgeSchematics.forEach((item) => {
                const key = String(item.source || '').trim();
                if (grouped[key]) {
                    grouped[key].push(item);
                } else {
                    grouped.other.push(item);
                }
            });

            const renderCard = (item) => {
                const title = htmlEscape(iconForgeSafeText(item.title, 'Icon target'));
                const where = htmlEscape(iconForgeSafeText(item.where, 'unknown location'));
                const targetType = htmlEscape(iconForgeSafeText(item.targetType, 'unknown'));
                const target = htmlEscape(iconForgeSafeText(item.target, 'unknown'));
                const icon = htmlEscape(iconForgeSafeText(item.icon, 'not set'));
                const id = htmlEscape(String(item.id || 'new'));
                const previewUrl = iconForgeBuildPreviewUrl(item.icon);
                const preview = previewUrl
                    ? ('<div class="iconforge-schematic-preview"><img src="' + htmlEscape(previewUrl) + '" alt="icon preview for ' + title + '" loading="lazy" /></div><div class="iconforge-schematic-hint">Hover to zoom</div>')
                    : '<div class="iconforge-schematic-preview"><span class="iconforge-schematic-preview-empty">No Icon</span></div>';
                return '<div class="iconforge-schematic-card">'
                    + '<h4>' + title + '</h4>'
                    + preview
                    + '<div class="iconforge-schematic-meta">goes to: ' + where + '</div>'
                    + '<div class="iconforge-schematic-meta">type: ' + targetType + '</div>'
                    + '<div class="iconforge-schematic-meta">target: ' + target + '</div>'
                    + '<div class="iconforge-schematic-meta">icon: ' + icon + '</div>'
                    + '<button onclick="openIconForgeEditorFromSchematic(\\\'' + id + '\\\')">Change This Icon</button>'
                    + '</div>';
            };

            const sectionsHtml = sectionConfig.map((section) => {
                const entries = grouped[section.key] || [];
                if (!entries.length) return '';
                const collapsed = iconForgeSectionIsCollapsed(section.key);
                const btn = collapsed ? 'Expand' : 'Collapse';
                const sectionClass = collapsed ? 'iconforge-schematic-section collapsed' : 'iconforge-schematic-section';
                return '<div class="' + sectionClass + '">'
                    + '<div class="iconforge-schematic-section-head">'
                    + '<h3>' + htmlEscape(section.label) + '</h3>'
                    + '<button class="iconforge-schematic-toggle" onclick="iconForgeToggleSection(\\\'' + htmlEscape(section.key) + '\\\')">' + btn + '</button>'
                    + '</div>'
                    + '<div class="iconforge-schematic-section-grid">'
                    + entries.map(renderCard).join('')
                    + '</div>'
                    + '</div>';
            }).join('');

            const otherHtml = (grouped.other || []).length
                ? (() => {
                    const otherKey = 'other';
                    const collapsed = iconForgeSectionIsCollapsed(otherKey);
                    const btn = collapsed ? 'Expand' : 'Collapse';
                    const sectionClass = collapsed ? 'iconforge-schematic-section collapsed' : 'iconforge-schematic-section';
                    return '<div class="' + sectionClass + '">'
                    + '<div class="iconforge-schematic-section-head">'
                    + '<h3>Other Icon Targets</h3>'
                    + '<button class="iconforge-schematic-toggle" onclick="iconForgeToggleSection(\\\'' + otherKey + '\\\')">' + btn + '</button>'
                    + '</div>'
                    + '<div class="iconforge-schematic-section-grid">'
                    + grouped.other.map(renderCard).join('')
                    + '</div>'
                    + '</div>';
                })()
                : '';

            gridRoot.innerHTML = sectionsHtml + otherHtml;
        }

        function showIconForgeSchematics() {
            const mapPanel = document.getElementById('iconforge_schematics_panel');
            const editorPanel = document.getElementById('iconforge_editor_panel');
            if (mapPanel) mapPanel.style.display = '';
            if (editorPanel) editorPanel.style.display = 'none';
            renderIconForgeSchematics();
            setIconStudioStatus('Icon schematics map ready. Click a target to change its icon.');
        }

        function showIconForgeEditor(contextLabel = '') {
            const mapPanel = document.getElementById('iconforge_schematics_panel');
            const editorPanel = document.getElementById('iconforge_editor_panel');
            const contextRoot = document.getElementById('iconforge_editor_context');
            if (mapPanel) mapPanel.style.display = 'none';
            if (editorPanel) editorPanel.style.display = '';
            if (contextRoot) contextRoot.textContent = contextLabel || 'Custom icon editor';
        }

        function openIconForgeEditorFromSchematic(schematicId) {
            const id = String(schematicId || '').trim();
            if (id === 'new') {
                showIconForgeEditor('New standalone icon');
                setIconStudioStatus('New icon editor opened.');
                return;
            }

            const entry = iconForgeSchematics.find((item) => String(item.id) === id);
            if (!entry) {
                showIconForgeEditor('Custom icon editor');
                return;
            }

            const studioName = document.getElementById('icon_studio_name');
            const targetType = document.getElementById('iconforge_target_type');
            const targetValue = document.getElementById('iconforge_target_value');
            const iconPath = document.getElementById('iconforge_icon_path');
            const source = String(entry.source || '').trim();
            const agentName = String(entry.agentName || '').trim();

            if (studioName) studioName.value = iconForgeInferStem(entry.icon, iconForgeInferStem(entry.target, 'iconforge_item'));
            if (targetType) {
                const nextType = String(entry.targetType || 'folder');
                const hasType = Array.from(targetType.options || []).some((opt) => String(opt.value) === nextType);
                if (hasType) targetType.value = nextType;
            }
            if (targetValue) targetValue.value = String(entry.target || '');
            if (iconPath) iconPath.value = String(entry.icon || '');

            if (source === 'wizard' || source === 'advanced') {
                iconForgeAgentContext = { active: true, source, agentName };
            }
            applyIconForgeAgentContextUI();

            showIconForgeEditor('Editing: ' + iconForgeSafeText(entry.title, 'selected target'));
            setIconStudioStatus('Editing icon target: ' + iconForgeSafeText(entry.target, 'unknown'));
        }

        function refreshIconForgeSchematics() {
            renderIconForgeSchematics();
        }

        function createIconStudioLayer(name = '') {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 256;
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            return {
                id: 'layer-' + String(iconStudioLayerSeed++),
                name: String(name || ('Layer ' + iconStudioLayerSeed)).trim(),
                visible: true,
                blendMode: 'source-over',
                opacity: 1,
                canvas,
                ctx,
            };
        }

        function iconStudioGetActiveLayer() {
            return iconStudioLayers[iconStudioActiveLayer] || null;
        }

        function iconStudioRenderLayers() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas || !iconStudioCtx) return;
            iconStudioCtx.clearRect(0, 0, canvas.width, canvas.height);
            iconStudioLayers.forEach((layer) => {
                if (!layer || !layer.visible) return;
                iconStudioCtx.save();
                iconStudioCtx.globalAlpha = Number.isFinite(layer.opacity) ? Math.max(0, Math.min(1, layer.opacity)) : 1;
                iconStudioCtx.globalCompositeOperation = String(layer.blendMode || 'source-over');
                iconStudioCtx.drawImage(layer.canvas, 0, 0);
                iconStudioCtx.restore();
            });
            iconStudioSyncActiveLayerControls();
            refreshIconStudioLayerList();
        }

        function iconStudioSyncActiveLayerControls() {
            const active = iconStudioGetActiveLayer();
            const nameInput = document.getElementById('icon_studio_layer_name');
            const blendSelect = document.getElementById('icon_studio_layer_blend');
            const opacitySlider = document.getElementById('icon_studio_layer_opacity');
            const opacityLabel = document.getElementById('icon_studio_layer_opacity_label');
            const hasLayer = !!active;
            const opacityPercent = hasLayer ? Math.round((Number(active.opacity) || 0) * 100) : 100;

            if (nameInput) {
                nameInput.disabled = !hasLayer;
                nameInput.value = hasLayer ? String(active.name || '') : '';
            }
            if (blendSelect) {
                blendSelect.disabled = !hasLayer;
                blendSelect.value = hasLayer ? String(active.blendMode || 'source-over') : 'source-over';
            }
            if (opacitySlider) {
                opacitySlider.disabled = !hasLayer;
                opacitySlider.value = String(Math.max(0, Math.min(100, opacityPercent)));
            }
            if (opacityLabel) {
                opacityLabel.textContent = String(Math.max(0, Math.min(100, opacityPercent))) + '%';
            }
        }

        function iconStudioRenameActiveLayer() {
            const active = iconStudioGetActiveLayer();
            const nameInput = document.getElementById('icon_studio_layer_name');
            if (!active || !nameInput) return;
            const nextName = String(nameInput.value || '').trim();
            if (!nextName) {
                setIconStudioStatus('Layer name cannot be empty.', true);
                iconStudioSyncActiveLayerControls();
                return;
            }
            active.name = nextName;
            refreshIconStudioLayerList();
            setIconStudioStatus('Layer renamed.');
        }

        function iconStudioSetActiveLayerBlend(mode) {
            const active = iconStudioGetActiveLayer();
            if (!active) return;
            active.blendMode = String(mode || 'source-over').trim() || 'source-over';
            iconStudioRenderLayers();
            setIconStudioStatus('Layer blend: ' + active.blendMode);
        }

        function iconStudioSetActiveLayerOpacity(rawValue) {
            const active = iconStudioGetActiveLayer();
            if (!active) return;
            const parsed = parseInt(String(rawValue ?? '100'), 10);
            const value = Number.isFinite(parsed) ? Math.max(0, Math.min(100, parsed)) : 100;
            active.opacity = value / 100;
            iconStudioRenderLayers();
        }

        function iconStudioMoveLayerTo(fromIndex, toIndex) {
            const from = Number(fromIndex);
            const to = Number(toIndex);
            if (!Number.isInteger(from) || !Number.isInteger(to)) return;
            if (from < 0 || to < 0 || from >= iconStudioLayers.length || to >= iconStudioLayers.length) return;
            if (from === to) return;
            const [layer] = iconStudioLayers.splice(from, 1);
            iconStudioLayers.splice(to, 0, layer);
            if (iconStudioActiveLayer === from) {
                iconStudioActiveLayer = to;
            } else if (iconStudioActiveLayer > from && iconStudioActiveLayer <= to) {
                iconStudioActiveLayer -= 1;
            } else if (iconStudioActiveLayer < from && iconStudioActiveLayer >= to) {
                iconStudioActiveLayer += 1;
            }
            iconStudioRenderLayers();
        }

        function iconStudioLayerDragStart(index, event) {
            const idx = Number(index);
            if (!Number.isInteger(idx)) return;
            iconStudioDraggingLayer = idx;
            if (event?.dataTransfer) {
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('text/plain', String(idx));
            }
        }

        function iconStudioLayerDragOver(index, event) {
            if (!event) return;
            event.preventDefault();
            if (event.dataTransfer) event.dataTransfer.dropEffect = 'move';
        }

        function iconStudioLayerDrop(index, event) {
            if (event) event.preventDefault();
            const to = Number(index);
            const from = iconStudioDraggingLayer;
            if (!Number.isInteger(from) || !Number.isInteger(to)) return;
            if (from < 0 || to < 0) return;
            iconStudioMoveLayerTo(from, to);
            iconStudioDraggingLayer = -1;
            setIconStudioStatus('Layer order updated.');
        }

        function iconStudioLayerDragEnd() {
            iconStudioDraggingLayer = -1;
        }

        function refreshIconStudioLayerList() {
            const root = document.getElementById('icon_studio_layer_list');
            if (!root) return;
            if (!iconStudioLayers.length) {
                root.innerHTML = 'No layers yet.';
                return;
            }
            root.innerHTML = iconStudioLayers.map((layer, idx) => {
                const active = idx === iconStudioActiveLayer;
                const eye = layer.visible ? 'visible' : 'hidden';
                const blend = String(layer.blendMode || 'source-over');
                const opacity = Math.round((Number(layer.opacity) || 0) * 100);
                const border = active ? 'border-color: rgba(212,168,87,0.8);' : '';
                const bg = active ? 'background: rgba(34,30,20,0.75);' : 'background: rgba(14,14,19,0.85);';
                return '<div style="display:flex; align-items:center; justify-content:space-between; gap:8px; border:1px solid #2b2f3a; border-radius:6px; padding:4px 6px; margin-bottom:4px; ' + border + bg + '" draggable="true" ondragstart="iconStudioLayerDragStart(' + idx + ', event)" ondragover="iconStudioLayerDragOver(' + idx + ', event)" ondrop="iconStudioLayerDrop(' + idx + ', event)" ondragend="iconStudioLayerDragEnd()">'
                    + '<button style="flex:1 1 auto; text-align:left; min-height:24px; padding:2px 6px;" onclick="iconStudioSelectLayer(' + idx + ')">' + htmlEscape(layer.name) + '</button>'
                    + '<span class="muted" style="font-size:11px;">' + eye + ' • ' + htmlEscape(blend) + ' • ' + String(Math.max(0, Math.min(100, opacity))) + '%</span>'
                    + '</div>';
            }).join('');
        }

        function iconStudioResetLayers() {
            iconStudioLayers = [createIconStudioLayer('Base')];
            iconStudioActiveLayer = 0;
            iconStudioUndo = [];
            iconStudioRenderLayers();
        }

        function iconStudioSelectLayer(index) {
            const idx = Number(index);
            if (!Number.isInteger(idx) || idx < 0 || idx >= iconStudioLayers.length) return;
            iconStudioActiveLayer = idx;
            iconStudioRenderLayers();
        }

        function iconStudioAddLayer() {
            iconStudioLayers.push(createIconStudioLayer('Layer ' + (iconStudioLayers.length + 1)));
            iconStudioActiveLayer = iconStudioLayers.length - 1;
            iconStudioRenderLayers();
            setIconStudioStatus('Layer added.');
        }

        function iconStudioDuplicateLayer() {
            const active = iconStudioGetActiveLayer();
            if (!active || !active.ctx) return;
            const dup = createIconStudioLayer(active.name + ' Copy');
            dup.ctx.drawImage(active.canvas, 0, 0);
            dup.blendMode = String(active.blendMode || 'source-over');
            dup.opacity = Number.isFinite(active.opacity) ? Math.max(0, Math.min(1, active.opacity)) : 1;
            iconStudioLayers.splice(iconStudioActiveLayer + 1, 0, dup);
            iconStudioActiveLayer += 1;
            iconStudioRenderLayers();
            setIconStudioStatus('Layer duplicated.');
        }

        function iconStudioDeleteLayer() {
            if (iconStudioLayers.length <= 1) {
                setIconStudioStatus('Cannot delete the last layer.', true);
                return;
            }
            iconStudioLayers.splice(iconStudioActiveLayer, 1);
            iconStudioActiveLayer = Math.max(0, Math.min(iconStudioActiveLayer, iconStudioLayers.length - 1));
            iconStudioRenderLayers();
            setIconStudioStatus('Layer deleted.');
        }

        function iconStudioMoveLayer(direction) {
            const dir = Number(direction) < 0 ? -1 : 1;
            const from = iconStudioActiveLayer;
            const to = from + dir;
            if (to < 0 || to >= iconStudioLayers.length) return;
            iconStudioMoveLayerTo(from, to);
            setIconStudioStatus('Layer order updated.');
        }

        function iconStudioToggleActiveLayerVisibility() {
            const active = iconStudioGetActiveLayer();
            if (!active) return;
            active.visible = !active.visible;
            iconStudioRenderLayers();
            setIconStudioStatus('Layer visibility: ' + (active.visible ? 'visible' : 'hidden'));
        }

        function readIconFxControls() {
            const strengthRaw = parseInt(document.getElementById('icon_fx_strength')?.value || '55', 10);
            const passesRaw = parseInt(document.getElementById('icon_fx_passes')?.value || '1', 10);
            const strength = Number.isFinite(strengthRaw) ? Math.max(1, Math.min(100, strengthRaw)) : 55;
            const passes = Number.isFinite(passesRaw) ? Math.max(1, Math.min(5, passesRaw)) : 1;
            return { strength, passes };
        }

        function updateIconFxControlLabels() {
            const { strength, passes } = readIconFxControls();
            const s = document.getElementById('icon_fx_strength_label');
            const p = document.getElementById('icon_fx_passes_label');
            if (s) s.textContent = String(strength) + '%';
            if (p) p.textContent = String(passes) + 'x';
        }

        function closeIconForgeMenus() {
            document.querySelectorAll('[data-iconforge-menu]').forEach((menu) => {
                menu.classList.remove('open');
            });
        }

        function toggleIconForgeMenu(button, event) {
            if (event) {
                event.preventDefault();
                event.stopPropagation();
            }
            const menu = button ? button.closest('[data-iconforge-menu]') : null;
            if (!menu) return;
            const shouldOpen = !menu.classList.contains('open');
            closeIconForgeMenus();
            if (shouldOpen) menu.classList.add('open');
        }

        function isTypingTarget(target) {
            const tag = String(target?.tagName || '').toLowerCase();
            return tag === 'input' || tag === 'textarea' || tag === 'select' || !!target?.isContentEditable;
        }

        document.addEventListener('keydown', (event) => {
            if (currentView !== 'view_iconforge') return;
            if (event.key === 'Escape') {
                closeIconForgeMenus();
                return;
            }

            const ctrlLike = event.ctrlKey || event.metaKey;
            if (!ctrlLike) return;

            const key = String(event.key || '').toLowerCase();
            const shift = !!event.shiftKey;
            const typing = isTypingTarget(event.target);

            if (!shift && key === 'z') {
                event.preventDefault();
                closeIconForgeMenus();
                iconStudioUndoStroke();
                return;
            }

            if (typing) return;

            if (!shift && key === 'n') {
                event.preventDefault();
                closeIconForgeMenus();
                iconStudioClearCanvas();
                setIconStudioStatus('New canvas ready.');
                return;
            }
            if (!shift && key === 'o') {
                event.preventDefault();
                closeIconForgeMenus();
                triggerIconStudioImport();
                return;
            }
            if (!shift && key === 's') {
                event.preventDefault();
                closeIconForgeMenus();
                saveIconStudioDraft();
                return;
            }
            if (shift && key === 'l') {
                event.preventDefault();
                closeIconForgeMenus();
                loadIconStudioDraft();
                return;
            }
            if (!shift && key === 'l') {
                event.preventDefault();
                closeIconForgeMenus();
                iconStudioClearCanvas();
                return;
            }
            if (shift && key === 'p') {
                event.preventDefault();
                closeIconForgeMenus();
                downloadIconStudioPng();
                return;
            }
            if (shift && key === 's') {
                event.preventDefault();
                closeIconForgeMenus();
                saveIconStudioIco();
                return;
            }
            if (shift && key === 'g') {
                event.preventDefault();
                closeIconForgeMenus();
                saveIconStudioAnimated();
                return;
            }
            if (!shift && key === 'i') {
                event.preventDefault();
                closeIconForgeMenus();
                applyIconStudioFx('invert');
                return;
            }
            if (shift && key === 'c') {
                event.preventDefault();
                closeIconForgeMenus();
                applyIconStudioFx('contrast');
                return;
            }
            if (shift && key === '1') {
                event.preventDefault();
                closeIconForgeMenus();
                applyIconStudioFx('grayscale');
            }
        });

        document.addEventListener('click', (event) => {
            const target = event && event.target;
            const insideMenu = target && typeof target.closest === 'function' ? target.closest('[data-iconforge-menu]') : null;
            if (!insideMenu) closeIconForgeMenus();
        });

        function iconStudioBuildDraftPayload() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return null;
            return {
                image_data: canvas.toDataURL('image/png'),
                icon_name: (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim(),
                target: (document.getElementById('icon_studio_target')?.value || 'standalone').trim(),
                tool: (document.getElementById('icon_studio_tool')?.value || 'brush').trim(),
                color: (document.getElementById('icon_studio_color')?.value || '#d4a857').trim(),
                size: (document.getElementById('icon_studio_size')?.value || '10').trim(),
                anim_preset: (document.getElementById('icon_studio_anim_preset')?.value || 'pulse').trim(),
                anim_seconds: (document.getElementById('icon_studio_anim_seconds')?.value || '3').trim(),
                anim_fps: (document.getElementById('icon_studio_anim_fps')?.value || '12').trim(),
                saved_at: new Date().toISOString(),
            };
        }

        function saveIconStudioDraft(showStatus = true) {
            try {
                const payload = iconStudioBuildDraftPayload();
                if (!payload) return;
                localStorage.setItem(ICON_STUDIO_DRAFT_KEY, JSON.stringify(payload));
                if (showStatus) setIconStudioStatus('Draft saved locally.');
            } catch (err) {
                if (showStatus) setIconStudioStatus('Draft save failed: ' + String(err), true);
            }
        }

        async function loadIconStudioDraft(showStatus = true) {
            const canvas = document.getElementById('icon_studio_canvas');
            const active = iconStudioGetActiveLayer();
            if (!canvas || !active || !active.ctx) return;
            try {
                const raw = localStorage.getItem(ICON_STUDIO_DRAFT_KEY);
                if (!raw) {
                    if (showStatus) setIconStudioStatus('No saved draft found.');
                    return;
                }
                const payload = JSON.parse(raw);
                if (!payload || typeof payload !== 'object' || !String(payload.image_data || '').startsWith('data:image/')) {
                    if (showStatus) setIconStudioStatus('Saved draft is invalid.', true);
                    return;
                }
                const img = new Image();
                await new Promise((resolve, reject) => {
                    img.onload = () => resolve();
                    img.onerror = () => reject(new Error('saved draft image failed to load'));
                    img.src = payload.image_data;
                });
                active.ctx.clearRect(0, 0, canvas.width, canvas.height);
                active.ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                iconStudioRenderLayers();

                const nameEl = document.getElementById('icon_studio_name');
                const targetEl = document.getElementById('icon_studio_target');
                const toolEl = document.getElementById('icon_studio_tool');
                const colorEl = document.getElementById('icon_studio_color');
                const sizeEl = document.getElementById('icon_studio_size');
                const sizeLabelEl = document.getElementById('icon_studio_size_label');
                const animPresetEl = document.getElementById('icon_studio_anim_preset');
                const animSecondsEl = document.getElementById('icon_studio_anim_seconds');
                const animFpsEl = document.getElementById('icon_studio_anim_fps');
                if (nameEl && payload.icon_name) nameEl.value = String(payload.icon_name);
                if (targetEl && payload.target && iconForgeAgentContext.active) targetEl.value = String(payload.target);
                if (toolEl && payload.tool) toolEl.value = String(payload.tool);
                if (colorEl && payload.color) colorEl.value = String(payload.color);
                if (sizeEl && payload.size) sizeEl.value = String(payload.size);
                if (sizeLabelEl && sizeEl) sizeLabelEl.textContent = String(parseInt(sizeEl.value || '10', 10)) + 'px';
                if (animPresetEl && payload.anim_preset) animPresetEl.value = String(payload.anim_preset);
                if (animSecondsEl && payload.anim_seconds) animSecondsEl.value = String(payload.anim_seconds);
                if (animFpsEl && payload.anim_fps) animFpsEl.value = String(payload.anim_fps);

                if (showStatus) setIconStudioStatus('Draft loaded.');
            } catch (err) {
                if (showStatus) setIconStudioStatus('Draft load failed: ' + String(err), true);
            }
        }

        function clearIconStudioDraft() {
            try {
                localStorage.removeItem(ICON_STUDIO_DRAFT_KEY);
                setIconStudioStatus('Saved draft cleared.');
            } catch (err) {
                setIconStudioStatus('Draft clear failed: ' + String(err), true);
            }
        }

        function downloadIconStudioPng() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            const stem = (document.getElementById('icon_studio_name')?.value || 'iconforge').trim() || 'iconforge';
            const safeStem = String(stem).replace(/[^a-zA-Z0-9._-]/g, '_');
            const a = document.createElement('a');
            a.href = canvas.toDataURL('image/png');
            a.download = safeStem + '.png';
            a.click();
            setIconStudioStatus('PNG downloaded.');
        }

        function iconStudioPushUndo() {
            if (!iconStudioLayers.length) return;
            const frame = {
                active: iconStudioActiveLayer,
                layers: iconStudioLayers.map((layer) => ({
                    name: layer.name,
                    visible: !!layer.visible,
                    blendMode: String(layer.blendMode || 'source-over'),
                    opacity: Number.isFinite(layer.opacity) ? Math.max(0, Math.min(1, layer.opacity)) : 1,
                    image: layer.ctx ? layer.ctx.getImageData(0, 0, layer.canvas.width, layer.canvas.height) : null,
                })),
            };
            iconStudioUndo.push(frame);
            if (iconStudioUndo.length > 25) iconStudioUndo.shift();
        }

        function iconStudioGetPointer(event, canvas) {
            const rect = canvas.getBoundingClientRect();
            const scaleX = canvas.width / rect.width;
            const scaleY = canvas.height / rect.height;
            return {
                x: (event.clientX - rect.left) * scaleX,
                y: (event.clientY - rect.top) * scaleY,
            };
        }

        function iconStudioCurrentStroke() {
            const color = document.getElementById('icon_studio_color')?.value || '#d4a857';
            const size = parseInt(document.getElementById('icon_studio_size')?.value || '10', 10);
            const tool = document.getElementById('icon_studio_tool')?.value || 'brush';
            return {
                color,
                size: Number.isFinite(size) ? Math.max(1, Math.min(64, size)) : 10,
                eraser: tool === 'eraser',
            };
        }

        function iconStudioStroke(from, to) {
            const active = iconStudioGetActiveLayer();
            if (!active || !active.ctx) return;
            const stroke = iconStudioCurrentStroke();
            const ctx = active.ctx;
            ctx.save();
            ctx.lineCap = 'round';
            ctx.lineJoin = 'round';
            ctx.lineWidth = stroke.size;
            ctx.globalCompositeOperation = stroke.eraser ? 'destination-out' : 'source-over';
            ctx.strokeStyle = stroke.color;
            ctx.beginPath();
            ctx.moveTo(from.x, from.y);
            ctx.lineTo(to.x, to.y);
            ctx.stroke();
            ctx.restore();
            iconStudioRenderLayers();
        }

        function initIconForgeStudio() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            if (iconStudioBooted) return;
            iconStudioCtx = canvas.getContext('2d', { willReadFrequently: true });
            if (!iconStudioCtx) return;
            iconStudioBooted = true;
            iconStudioResetLayers();
            applyIconForgeAgentContextUI();

            const slider = document.getElementById('icon_studio_size');
            const label = document.getElementById('icon_studio_size_label');
            if (slider && label) {
                const sync = () => {
                    label.textContent = String(parseInt(slider.value || '10', 10)) + 'px';
                };
                slider.addEventListener('input', sync);
                sync();
            }

            const fxStrength = document.getElementById('icon_fx_strength');
            const fxPasses = document.getElementById('icon_fx_passes');
            if (fxStrength) fxStrength.addEventListener('input', updateIconFxControlLabels);
            if (fxPasses) fxPasses.addEventListener('input', updateIconFxControlLabels);
            updateIconFxControlLabels();

            let lastPoint = { x: 0, y: 0 };
            canvas.addEventListener('pointerdown', (event) => {
                iconStudioPushUndo();
                iconStudioDrawing = true;
                lastPoint = iconStudioGetPointer(event, canvas);
                iconStudioStroke(lastPoint, lastPoint);
            });
            canvas.addEventListener('pointermove', (event) => {
                if (!iconStudioDrawing) return;
                const next = iconStudioGetPointer(event, canvas);
                iconStudioStroke(lastPoint, next);
                lastPoint = next;
            });
            const endDraw = () => {
                iconStudioDrawing = false;
                saveIconStudioDraft(false);
            };
            canvas.addEventListener('pointerup', endDraw);
            canvas.addEventListener('pointerleave', endDraw);
            loadIconStudioDraft(false);
            setIconStudioStatus('Studio ready. Autosave enabled.');
        }

        function triggerIconStudioImport() {
            const file = document.getElementById('icon_studio_import_file');
            if (file) file.click();
        }

        async function handleIconStudioImport(event) {
            const file = event?.target?.files?.[0];
            const canvas = document.getElementById('icon_studio_canvas');
            const active = iconStudioGetActiveLayer();
            if (!file || !canvas || !active || !active.ctx) return;
            try {
                const objectUrl = URL.createObjectURL(file);
                const img = new Image();
                await new Promise((resolve, reject) => {
                    img.onload = () => resolve();
                    img.onerror = () => reject(new Error('image load failed'));
                    img.src = objectUrl;
                });
                iconStudioPushUndo();
                active.ctx.clearRect(0, 0, canvas.width, canvas.height);
                const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
                const drawW = Math.max(1, Math.floor(img.width * scale));
                const drawH = Math.max(1, Math.floor(img.height * scale));
                const offX = Math.floor((canvas.width - drawW) / 2);
                const offY = Math.floor((canvas.height - drawH) / 2);
                active.ctx.drawImage(img, offX, offY, drawW, drawH);
                URL.revokeObjectURL(objectUrl);
                iconStudioRenderLayers();
                saveIconStudioDraft(false);
                setIconStudioStatus('Imported image: ' + file.name);
            } catch (err) {
                setIconStudioStatus('Import failed: ' + String(err), true);
            }
        }

        function iconStudioUndoStroke() {
            if (!iconStudioCtx) return;
            const frame = iconStudioUndo.pop();
            if (!frame) {
                setIconStudioStatus('Undo stack is empty.');
                return;
            }
            if (Array.isArray(frame.layers) && frame.layers.length) {
                iconStudioLayers = frame.layers.map((layerFrame, idx) => {
                    const layer = createIconStudioLayer(layerFrame?.name || ('Layer ' + (idx + 1)));
                    layer.visible = layerFrame?.visible !== false;
                    layer.blendMode = String(layerFrame?.blendMode || 'source-over');
                    const opacityValue = Number(layerFrame?.opacity);
                    layer.opacity = Number.isFinite(opacityValue) ? Math.max(0, Math.min(1, opacityValue)) : 1;
                    if (layer.ctx && layerFrame?.image) layer.ctx.putImageData(layerFrame.image, 0, 0);
                    return layer;
                });
                iconStudioActiveLayer = Math.max(0, Math.min(Number(frame.active) || 0, iconStudioLayers.length - 1));
                iconStudioRenderLayers();
            }
            saveIconStudioDraft(false);
            setIconStudioStatus('Undo applied.');
        }

        function iconStudioClearCanvas() {
            const canvas = document.getElementById('icon_studio_canvas');
            const active = iconStudioGetActiveLayer();
            if (!canvas || !active || !active.ctx) return;
            iconStudioPushUndo();
            active.ctx.clearRect(0, 0, canvas.width, canvas.height);
            iconStudioRenderLayers();
            saveIconStudioDraft(false);
            setIconStudioStatus('Canvas cleared.');
        }

        function iconStudioFillBackground() {
            const canvas = document.getElementById('icon_studio_canvas');
            const active = iconStudioGetActiveLayer();
            if (!canvas || !active || !active.ctx) return;
            const color = document.getElementById('icon_studio_color')?.value || '#1d3557';
            iconStudioPushUndo();
            active.ctx.save();
            active.ctx.globalCompositeOperation = 'source-over';
            active.ctx.fillStyle = color;
            active.ctx.fillRect(0, 0, canvas.width, canvas.height);
            active.ctx.restore();
            iconStudioRenderLayers();
            saveIconStudioDraft(false);
            setIconStudioStatus('Background filled.');
        }

        function applyIconStudioFx(kind) {
            const canvas = document.getElementById('icon_studio_canvas');
            const active = iconStudioGetActiveLayer();
            if (!canvas || !active || !active.ctx) return;
            iconStudioPushUndo();
            const image = active.ctx.getImageData(0, 0, canvas.width, canvas.height);
            const data = image.data;
            const width = canvas.width;
            const height = canvas.height;
            const source = new Uint8ClampedArray(data);
            const controls = readIconFxControls();
            const strengthScale = controls.strength / 100;
            const passes = controls.passes;

            const clampByte = (v) => Math.max(0, Math.min(255, Math.round(v)));
            const hex = String(document.getElementById('icon_studio_color')?.value || '#d4a857').trim();
            const glowRgb = /^#[0-9a-fA-F]{6}$/.test(hex)
                ? [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)]
                : [212, 168, 87];

            function sampleNearest(buffer, x, y) {
                const sx = Math.max(0, Math.min(width - 1, Math.round(x)));
                const sy = Math.max(0, Math.min(height - 1, Math.round(y)));
                const idx = (sy * width + sx) * 4;
                return [buffer[idx], buffer[idx + 1], buffer[idx + 2], buffer[idx + 3]];
            }

            function alphaBlurAt(buffer, x, y) {
                let sum = 0;
                let weightSum = 0;
                for (let oy = -1; oy <= 1; oy += 1) {
                    for (let ox = -1; ox <= 1; ox += 1) {
                        const sx = Math.max(0, Math.min(width - 1, x + ox));
                        const sy = Math.max(0, Math.min(height - 1, y + oy));
                        const idx = (sy * width + sx) * 4 + 3;
                        const weight = (ox === 0 && oy === 0) ? 4 : ((ox === 0 || oy === 0) ? 2 : 1);
                        sum += buffer[idx] * weight;
                        weightSum += weight;
                    }
                }
                return sum / Math.max(1, weightSum);
            }

            for (let pass = 0; pass < passes; pass += 1) {
                for (let i = 0; i < data.length; i += 4) {
                    const r = data[i];
                    const g = data[i + 1];
                    const b = data[i + 2];
                    if (kind === 'grayscale') {
                        const y = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                        data[i] = clampByte(r * (1 - strengthScale) + y * strengthScale);
                        data[i + 1] = clampByte(g * (1 - strengthScale) + y * strengthScale);
                        data[i + 2] = clampByte(b * (1 - strengthScale) + y * strengthScale);
                    } else if (kind === 'invert') {
                        data[i] = clampByte(r * (1 - strengthScale) + (255 - r) * strengthScale);
                        data[i + 1] = clampByte(g * (1 - strengthScale) + (255 - g) * strengthScale);
                        data[i + 2] = clampByte(b * (1 - strengthScale) + (255 - b) * strengthScale);
                    } else if (kind === 'contrast') {
                        const c = 36 + Math.round(52 * strengthScale);
                        const factor = (259 * (c + 255)) / (255 * (259 - c));
                        data[i] = clampByte(factor * (r - 128) + 128);
                        data[i + 1] = clampByte(factor * (g - 128) + 128);
                        data[i + 2] = clampByte(factor * (b - 128) + 128);
                    } else if (kind === 'soften') {
                        data[i] = clampByte(r * (1 - strengthScale) + ((r + 255) / 2) * strengthScale);
                        data[i + 1] = clampByte(g * (1 - strengthScale) + ((g + 255) / 2) * strengthScale);
                        data[i + 2] = clampByte(b * (1 - strengthScale) + ((b + 255) / 2) * strengthScale);
                    }
                }
            }

            if (kind === 'glow_soft' || kind === 'glow_neon') {
                for (let y = 0; y < height; y += 1) {
                    for (let x = 0; x < width; x += 1) {
                        const idx = (y * width + x) * 4;
                        const baseR = source[idx];
                        const baseG = source[idx + 1];
                        const baseB = source[idx + 2];
                        const baseA = source[idx + 3];
                        const auraA = alphaBlurAt(source, x, y);

                        if (kind === 'glow_soft') {
                            const glowMix = (auraA / 255) * 0.55;
                            data[idx] = clampByte(baseR * (1 - glowMix) + glowRgb[0] * glowMix + 12);
                            data[idx + 1] = clampByte(baseG * (1 - glowMix) + glowRgb[1] * glowMix + 12);
                            data[idx + 2] = clampByte(baseB * (1 - glowMix) + glowRgb[2] * glowMix + 12);
                            data[idx + 3] = clampByte(Math.max(baseA, auraA * 0.9));
                        } else {
                            const edge = Math.max(0, auraA - baseA);
                            const neon = Math.min(1, edge / 190);
                            data[idx] = clampByte(baseR + glowRgb[0] * neon + 20 * neon);
                            data[idx + 1] = clampByte(baseG + glowRgb[1] * neon + 30 * neon);
                            data[idx + 2] = clampByte(baseB + glowRgb[2] * neon + 46 * neon);
                            data[idx + 3] = clampByte(Math.max(baseA, auraA));
                        }
                    }
                }
            } else if (kind === 'swirl_warp') {
                const out = new Uint8ClampedArray(data.length);
                const cx = width / 2;
                const cy = height / 2;
                const maxR = Math.max(1, Math.hypot(cx, cy));
                for (let y = 0; y < height; y += 1) {
                    for (let x = 0; x < width; x += 1) {
                        const dx = x - cx;
                        const dy = y - cy;
                        const r = Math.hypot(dx, dy);
                        const norm = Math.min(1, r / maxR);
                        const theta = Math.atan2(dy, dx);
                        const twist = (1 - norm) * (1 - norm) * 1.35;
                        const srcTheta = theta - twist;
                        const sx = cx + Math.cos(srcTheta) * r;
                        const sy = cy + Math.sin(srcTheta) * r;
                        const [rr, gg, bb, aa] = sampleNearest(source, sx, sy);
                        const idx = (y * width + x) * 4;
                        out[idx] = rr;
                        out[idx + 1] = gg;
                        out[idx + 2] = bb;
                        out[idx + 3] = aa;
                    }
                }
                data.set(out);
            } else if (kind === 'particle_swirl') {
                const out = new Uint8ClampedArray(source);
                const cx = width / 2;
                const cy = height / 2;
                const maxR = Math.min(width, height) * 0.42;
                const particles = 160;
                for (let p = 0; p < particles; p += 1) {
                    const t = p / particles;
                    const angle = t * Math.PI * 7.5;
                    const radius = maxR * Math.pow(t, 0.8);
                    const x = Math.round(cx + Math.cos(angle) * radius);
                    const y = Math.round(cy + Math.sin(angle) * radius * 0.7);
                    for (let oy = -1; oy <= 1; oy += 1) {
                        for (let ox = -1; ox <= 1; ox += 1) {
                            const px = x + ox;
                            const py = y + oy;
                            if (px < 0 || py < 0 || px >= width || py >= height) continue;
                            const idx = (py * width + px) * 4;
                            const strength = 1 - (Math.abs(ox) + Math.abs(oy)) / 3;
                            out[idx] = clampByte(out[idx] + glowRgb[0] * 0.42 * strength);
                            out[idx + 1] = clampByte(out[idx + 1] + glowRgb[1] * 0.46 * strength);
                            out[idx + 2] = clampByte(out[idx + 2] + glowRgb[2] * 0.62 * strength + 18 * strength);
                            out[idx + 3] = clampByte(Math.max(out[idx + 3], 145 * strength));
                        }
                    }
                }
                data.set(out);
            }

            active.ctx.putImageData(image, 0, 0);
            iconStudioRenderLayers();
            saveIconStudioDraft(false);
            setIconStudioStatus('Applied FX: ' + kind);
        }

        async function saveIconStudioIco() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            const iconName = (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim();
            const selectedTarget = (document.getElementById('icon_studio_target')?.value || 'standalone').trim();
            const target = iconForgeAgentContext.active ? selectedTarget : 'standalone';
            const payload = {
                icon_name: iconName,
                image_data: canvas.toDataURL('image/png'),
            };
            saveIconStudioDraft(false);
            setIconStudioStatus('Rendering multi-size .ico in IconForge...');
            const res = await fetch('/api/agentforge/icon/create_from_canvas', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!data || !data.ok) {
                setIconStudioStatus('Save failed: ' + String(data?.message || 'unknown error'), true);
                return;
            }
            const iconPath = String(data.icon || '');
            if (target === 'wizard' || target === 'both') {
                const wizardPath = document.getElementById('wizard_icon_path');
                const wizardMode = document.getElementById('wizard_icon_mode');
                if (wizardPath) wizardPath.value = iconPath;
                if (wizardMode) wizardMode.value = 'iconforge';
                setIconStatus('wizard_icon_status', 'Custom icon ready: ' + iconPath);
                toggleWizardIconSource();
            }
            if (target === 'advanced' || target === 'both') {
                const makerPath = document.getElementById('maker_icon_path');
                const makerMode = document.getElementById('maker_icon_mode');
                if (makerPath) makerPath.value = iconPath;
                if (makerMode) makerMode.value = 'iconforge';
                setIconStatus('maker_icon_status', 'Custom icon ready: ' + iconPath);
                toggleMakerIconSource();
            }
            if (target === 'standalone') {
                setIconStudioStatus('Saved icon (standalone): ' + iconPath + ' (sizes: 16,24,32,48,64,128,256)');
            } else {
                setIconStudioStatus('Saved icon: ' + iconPath + ' (sizes: 16,24,32,48,64,128,256)');
            }
            if (window.confirm('Icon saved. Are you done and want to return to the Icon Schematics map?')) {
                showIconForgeSchematics();
            }
        }

        async function saveIconStudioAnimated() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            const iconName = (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim();
            const selectedTarget = (document.getElementById('icon_studio_target')?.value || 'standalone').trim();
            const target = iconForgeAgentContext.active ? selectedTarget : 'standalone';
            const preset = (document.getElementById('icon_studio_anim_preset')?.value || 'pulse').trim();
            const seconds = parseInt(document.getElementById('icon_studio_anim_seconds')?.value || '3', 10);
            const fps = parseInt(document.getElementById('icon_studio_anim_fps')?.value || '12', 10);
            const payload = {
                icon_name: iconName,
                image_data: canvas.toDataURL('image/png'),
                preset,
                seconds: Number.isFinite(seconds) ? seconds : 3,
                fps: Number.isFinite(fps) ? fps : 12,
            };
            saveIconStudioDraft(false);
            setIconStudioStatus('Rendering animated GIF + ICO fallback...');
            const res = await fetch('/api/agentforge/icon/create_animated_from_canvas', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (!data || !data.ok) {
                setIconStudioStatus('Animated save failed: ' + String(data?.message || 'unknown error'), true);
                return;
            }

            const icoPath = String(data.icon || '');
            const gifPath = String(data.animated || '');
            if (target === 'wizard' || target === 'both') {
                const wizardPath = document.getElementById('wizard_icon_path');
                const wizardMode = document.getElementById('wizard_icon_mode');
                if (wizardPath) wizardPath.value = icoPath;
                if (wizardMode) wizardMode.value = 'iconforge';
                setIconStatus('wizard_icon_status', 'Custom icon ready: ' + icoPath);
                toggleWizardIconSource();
            }
            if (target === 'advanced' || target === 'both') {
                const makerPath = document.getElementById('maker_icon_path');
                const makerMode = document.getElementById('maker_icon_mode');
                if (makerPath) makerPath.value = icoPath;
                if (makerMode) makerMode.value = 'iconforge';
                setIconStatus('maker_icon_status', 'Custom icon ready: ' + icoPath);
                toggleMakerIconSource();
            }
            if (target === 'standalone') {
                setIconStudioStatus('Animated saved (standalone): ' + gifPath + ' | ICO fallback: ' + icoPath);
            } else {
                setIconStudioStatus('Animated saved: ' + gifPath + ' | ICO fallback: ' + icoPath);
            }
            if (window.confirm('Icon saved. Are you done and want to return to the Icon Schematics map?')) {
                showIconForgeSchematics();
            }
        }

        function setIconForgeFromStudioIco() {
            const path = document.getElementById('iconforge_icon_path');
            const name = (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim() || 'agent_forge_icon';
            if (!path) return;
            path.value = `assets/icons/agents/${name}.ico`;
            setIconStudioStatus('Set icon path from studio name. Use after Save .ico for the latest timestamped asset.');
        }

        async function refreshIconForgeOps() {
            const data = await fetchJsonWithTimeout('/api/iconforge/backups', 6000);
            const root = document.getElementById('iconforge_backups');
            if (!root) return;
            root.textContent = JSON.stringify(data, null, 2);
            iconForgeBackupsCache = (data && data.ok && data.items && typeof data.items === 'object') ? data.items : {};
            renderIconForgeSchematics();
        }

        async function applyWindowsIconOverride() {
            const targetType = (document.getElementById('iconforge_target_type')?.value || 'folder').trim();
            const target = (document.getElementById('iconforge_target_value')?.value || '').trim();
            const icon = (document.getElementById('iconforge_icon_path')?.value || '').trim();
            const resultRoot = document.getElementById('iconforge_ops_result');
            if (!target || !icon) {
                if (resultRoot) resultRoot.textContent = JSON.stringify({ ok: false, message: 'target and icon path are required' }, null, 2);
                return;
            }
            const res = await fetch('/api/iconforge/apply', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target_type: targetType, target, icon }),
            });
            const data = await res.json();
            if (resultRoot) resultRoot.textContent = JSON.stringify(data, null, 2);
            if (data && data.backup_key) {
                const restoreKey = document.getElementById('iconforge_restore_key');
                if (restoreKey) restoreKey.value = String(data.backup_key);
            }
            await refreshIconForgeOps();
        }

        async function refreshWindowsIconCache() {
            const resultRoot = document.getElementById('iconforge_ops_result');
            const res = await fetch('/api/iconforge/refresh_cache', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await res.json();
            if (resultRoot) resultRoot.textContent = JSON.stringify(data, null, 2);
        }

        async function restoreWindowsIconOverride() {
            const backupKey = (document.getElementById('iconforge_restore_key')?.value || '').trim();
            const resultRoot = document.getElementById('iconforge_ops_result');
            if (!backupKey) {
                if (resultRoot) resultRoot.textContent = JSON.stringify({ ok: false, message: 'backup key is required' }, null, 2);
                return;
            }
            const res = await fetch('/api/iconforge/restore', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ backup_key: backupKey }),
            });
            const data = await res.json();
            if (resultRoot) resultRoot.textContent = JSON.stringify(data, null, 2);
            await refreshIconForgeOps();
        }

        async function exportIconForgePack() {
            const outputDir = (document.getElementById('iconforge_pack_export_dir')?.value || '').trim();
            const resultRoot = document.getElementById('iconforge_ops_result');
            if (!outputDir) {
                if (resultRoot) resultRoot.textContent = JSON.stringify({ ok: false, message: 'export directory path is required' }, null, 2);
                return;
            }
            const res = await fetch('/api/iconforge/pack/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ output_dir: outputDir }),
            });
            const data = await res.json();
            if (resultRoot) resultRoot.textContent = JSON.stringify(data, null, 2);
        }

        async function importIconForgePack() {
            const source = (document.getElementById('iconforge_pack_import_source')?.value || '').trim();
            const applyChanges = !!document.getElementById('iconforge_pack_apply')?.checked;
            const refreshCache = !!document.getElementById('iconforge_pack_refresh')?.checked;
            const resultRoot = document.getElementById('iconforge_ops_result');
            if (!source) {
                if (resultRoot) resultRoot.textContent = JSON.stringify({ ok: false, message: 'import source is required' }, null, 2);
                return;
            }
            const res = await fetch('/api/iconforge/pack/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ source, apply_changes: applyChanges, refresh_cache: refreshCache }),
            });
            const data = await res.json();
            if (resultRoot) resultRoot.textContent = JSON.stringify(data, null, 2);
            await refreshIconForgeOps();
        }

        function personalityDefinitions() {
            return {
                balanced: {
                    title: 'Balanced Arbiter',
                    directives: 'Weigh speed, risk, and confidence evenly. Prefer stable outcomes and clear handoffs.'
                },
                decisive: {
                    title: 'Decisive Executor',
                    directives: 'Prioritize fast closure and clear ownership. Escalate only when blockers are hard.'
                },
                cautious: {
                    title: 'Cautious Guardian',
                    directives: 'Prioritize safety and reversibility. Validate assumptions before irreversible actions.'
                },
                creative: {
                    title: 'Creative Pathfinder',
                    directives: 'Generate multiple approaches and choose the highest expected value with low churn.'
                },
                analytical: {
                    title: 'Analytical Strategist',
                    directives: 'Use structured reasoning, measurable criteria, and deterministic decision logs.'
                },
                introvert_local: {
                    title: 'Local Quiet Ranger',
                    directives: 'Prefer quiet local autonomy over remote chatter. Hunt and fix host/LAN incidents proactively without social contention.'
                }
            };
        }

        function selectedBehaviorPatterns(selectId) {
            const el = document.getElementById(selectId);
            if (!el) return [];
            return Array.from(el.selectedOptions || [])
                .map((option) => String(option.value || '').trim().toLowerCase())
                .filter((value) => !!value);
        }

        function composeSystemWithPersonality(baseSystem, preset, notes) {
            const key = String(preset || 'balanced').trim().toLowerCase();
            const def = personalityDefinitions()[key] || personalityDefinitions().balanced;
            const marker = '\\n\\nPersonality Wrapper (';
            const rawRoot = String(baseSystem || '').trim();
            const markerIndex = rawRoot.indexOf(marker);
            const root = (markerIndex >= 0 ? rawRoot.slice(0, markerIndex).trim() : rawRoot) || 'You are a helpful specialist agent.';
            const extraNotes = String(notes || '').trim();
            const deterministicClaimProtocol = [
                'Job Claim Protocol:',
                '1) Do not argue with peer agents over first-claim ownership.',
                '2) Claim by oldest queue timestamp first.',
                '3) If timestamps tie, lowest lexicographic agent id wins claim.',
                '4) If not selected, immediately yield and take next eligible job.',
            ].join(' ');
            const personalityBlock = [
                `Personality Wrapper (${def.title}).`,
                def.directives,
                deterministicClaimProtocol,
                extraNotes ? `Operator Notes: ${extraNotes}` : ''
            ].filter((x) => !!x).join(' ');
            return `${root}\n\n${personalityBlock}`.trim();
        }

        function rankCaps(rank) {
            const caps = {
                cadet: { skills: 4, sigils: 3, mcp: 5 },
                specialist: { skills: 5, sigils: 3, mcp: 6 },
                lieutenant: { skills: 6, sigils: 4, mcp: 7 },
                captain: { skills: 8, sigils: 5, mcp: 9 },
                commander: { skills: 10, sigils: 6, mcp: 11 },
                general: { skills: 12, sigils: 7, mcp: 13 },
                admiral: { skills: 15, sigils: 8, mcp: 15 },
            };
            return caps[String(rank || '').trim().toLowerCase()] || { skills: 4, sigils: 3, mcp: 5 };
        }

        function selectedWizardValues(selectId) {
            const el = document.getElementById(selectId);
            if (!el) return [];
            return Array.from(el.selectedOptions || []).map((option) => String(option.value || '').trim().toLowerCase()).filter((x) => !!x);
        }

        function switchAgentForgeMode(mode) {
            const wizard = document.getElementById('maker_wizard_mode');
            const advanced = document.getElementById('maker_advanced_mode');
            const wizardBtn = document.getElementById('maker_mode_wizard_btn');
            const advancedBtn = document.getElementById('maker_mode_advanced_btn');
            if (!wizard || !advanced) return;
            const useWizard = mode !== 'advanced';
            wizard.style.display = useWizard ? 'block' : 'none';
            advanced.style.display = useWizard ? 'none' : 'block';
            if (wizardBtn) wizardBtn.style.opacity = useWizard ? '1' : '0.65';
            if (advancedBtn) advancedBtn.style.opacity = useWizard ? '0.65' : '1';
            if (useWizard) setWizardStep(1);
            if (!useWizard) syncAdvancedPolicyAwareness();
        }

        function wizardSummary() {
            return {
                name: (document.getElementById('wizard_name')?.value || '').trim(),
                endpoint: (document.getElementById('wizard_endpoint')?.value || '').trim(),
                role_focus: (document.getElementById('wizard_role_focus')?.value || '').trim(),
                scope: (document.getElementById('wizard_scope')?.value || '').trim(),
                behavior: (document.getElementById('wizard_behavior')?.value || '').trim(),
                power: (document.getElementById('wizard_power')?.value || '').trim(),
                personality: (document.getElementById('wizard_personality')?.value || '').trim(),
                personality_notes: (document.getElementById('wizard_personality_notes')?.value || '').trim(),
                personality_interests: parseCsvTags(document.getElementById('wizard_personality_interests')?.value || ''),
                behavior_patterns: selectedBehaviorPatterns('wizard_behavior_patterns'),
                skills: selectedWizardValues('wizard_skill_list'),
                sigils: selectedWizardValues('wizard_sigil_list'),
                state_machine_template: (document.getElementById('wizard_state_machine_template')?.value || 'none').trim(),
                icon_mode: (document.getElementById('wizard_icon_mode')?.value || 'none').trim(),
                icon_path: (document.getElementById('wizard_icon_path')?.value || '').trim(),
                encrypt_profile: !!document.getElementById('wizard_encrypt_profile')?.checked,
            };
        }

        function updateWizardReview() {
            const root = document.getElementById('wizard_review');
            if (!root) return;
            root.textContent = JSON.stringify(wizardSummary(), null, 2);
        }

        function updateWizardChecklist() {
            document.querySelectorAll('[data-check-step]').forEach((btn) => {
                const step = Number(btn.getAttribute('data-check-step') || '0');
                btn.classList.toggle('is-active', step === wizardStep);
                btn.classList.toggle('is-complete', step < wizardStep);
                const dot = btn.querySelector('.step-dot');
                if (dot) dot.textContent = step < wizardStep ? '✓' : String(step);
            });
        }

        function setWizardStep(step) {
            const bounded = Math.max(1, Math.min(WIZARD_TOTAL_STEPS, Number(step) || 1));
            wizardStep = bounded;
            document.querySelectorAll('[data-wizard-step]').forEach((node) => {
                const nodeStep = Number(node.getAttribute('data-wizard-step') || '0');
                node.style.display = nodeStep === wizardStep ? 'block' : 'none';
            });
            const label = document.getElementById('wizard_step_label');
            if (label) {
                const names = ['Identity', 'Profile', 'Capabilities', 'Review'];
                label.textContent = `Step ${wizardStep} of ${WIZARD_TOTAL_STEPS}: ${names[wizardStep - 1]}`;
            }
            const backBtn = document.getElementById('wizard_back_btn');
            const nextBtn = document.getElementById('wizard_next_btn');
            const reviewBtn = document.getElementById('wizard_review_btn');
            const createBtn = document.getElementById('wizard_create_btn');
            if (backBtn) backBtn.disabled = wizardStep <= 1;
            if (nextBtn) nextBtn.style.display = wizardStep < WIZARD_TOTAL_STEPS ? '' : 'none';
            if (reviewBtn) reviewBtn.style.display = wizardStep < WIZARD_TOTAL_STEPS ? '' : 'none';
            if (createBtn) createBtn.style.display = wizardStep === WIZARD_TOTAL_STEPS ? '' : 'none';
            updateWizardChecklist();
            if (wizardStep === WIZARD_TOTAL_STEPS) updateWizardReview();
        }

        function wizardNextStep() {
            setWizardStep(wizardStep + 1);
        }

        function wizardPrevStep() {
            setWizardStep(wizardStep - 1);
        }

        function wizardOpenReview() {
            setWizardStep(WIZARD_TOTAL_STEPS);
        }

        const STATE_MACHINE_TEMPLATES = {
            none: {
                label: 'none',
                description: 'No predefined state machine. Agent can run with default runtime behavior.',
                machine: null,
            },
            basic_lifecycle: {
                label: 'basic lifecycle',
                description: 'Simple work loop: Idle -> Executing -> Completed/Blocked.',
                machine: {
                    initial_state: 'Idle',
                    states: {
                        Idle: { on_task: 'Executing' },
                        Executing: { on_success: 'Completed', on_error: 'Blocked' },
                        Completed: { on_task: 'Executing' },
                        Blocked: { on_retry: 'Executing', on_abort: 'Idle' },
                    },
                },
            },
            delegation_flow: {
                label: 'delegation flow',
                description: 'Delegation-aware flow with planning and verification stages.',
                machine: {
                    initial_state: 'Idle',
                    states: {
                        Idle: { on_task: 'Planning' },
                        Planning: { on_ready: 'Delegating', on_error: 'Blocked' },
                        Delegating: { on_dispatched: 'Executing', on_error: 'Blocked' },
                        Executing: { on_partial: 'Delegating', on_success: 'Verifying', on_error: 'Blocked' },
                        Verifying: { on_pass: 'Completed', on_fail: 'Blocked' },
                        Completed: { on_task: 'Planning' },
                        Blocked: { on_retry: 'Planning', on_abort: 'Idle' },
                    },
                },
            },
            incident_response: {
                label: 'incident response',
                description: 'Incident triage and mitigation loop for operational agents.',
                machine: {
                    initial_state: 'Idle',
                    states: {
                        Idle: { on_incident: 'Triage' },
                        Triage: { on_classified: 'Mitigation', on_escalate: 'Blocked' },
                        Mitigation: { on_fixed: 'Validation', on_failed: 'Blocked' },
                        Validation: { on_pass: 'Completed', on_fail: 'Mitigation' },
                        Completed: { on_incident: 'Triage' },
                        Blocked: { on_retry: 'Triage', on_abort: 'Idle' },
                    },
                },
            },
        };

        function cloneTemplateMachine(machine) {
            if (!machine || typeof machine !== 'object') return null;
            return JSON.parse(JSON.stringify(machine));
        }

        function getTemplateMeta(templateId) {
            const key = String(templateId || 'none').trim();
            return STATE_MACHINE_TEMPLATES[key] || STATE_MACHINE_TEMPLATES.none;
        }

        function syncWizardStateMachinePreview() {
            const templateId = (document.getElementById('wizard_state_machine_template')?.value || 'none').trim();
            const meta = getTemplateMeta(templateId);
            const hint = document.getElementById('wizard_state_machine_hint');
            if (hint) hint.textContent = meta.description;
        }

        function applySelectedStateMachineTemplate() {
            const templateId = (document.getElementById('maker_state_machine_template')?.value || 'none').trim();
            const meta = getTemplateMeta(templateId);
            const root = document.getElementById('maker_state_machine_json');
            const hint = document.getElementById('maker_state_machine_hint');
            if (root) {
                if (!meta.machine) {
                    root.value = '';
                } else {
                    root.value = JSON.stringify(cloneTemplateMachine(meta.machine), null, 2);
                }
            }
            if (hint) hint.textContent = meta.description;
        }

        function clearStateMachineJson() {
            const root = document.getElementById('maker_state_machine_json');
            const sel = document.getElementById('maker_state_machine_template');
            const hint = document.getElementById('maker_state_machine_hint');
            if (root) root.value = '';
            if (sel) sel.value = 'none';
            if (hint) hint.textContent = STATE_MACHINE_TEMPLATES.none.description;
        }

        function formatStateMachineJson() {
            const root = document.getElementById('maker_state_machine_json');
            if (!root) return;
            const raw = String(root.value || '').trim();
            if (!raw) return;
            try {
                const obj = JSON.parse(raw);
                root.value = JSON.stringify(obj, null, 2);
            } catch {
                alert('State machine JSON is invalid.');
            }
        }

        function parseAdvancedStateMachine() {
            const raw = String(document.getElementById('maker_state_machine_json')?.value || '').trim();
            if (!raw) return null;
            let parsed;
            try {
                parsed = JSON.parse(raw);
            } catch {
                alert('State machine JSON must be valid JSON.');
                throw new Error('invalid state machine json');
            }
            if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
                alert('State machine must be a JSON object.');
                throw new Error('invalid state machine object');
            }
            return parsed;
        }

        function setMakerPolicyChips(chips) {
            const root = document.getElementById('maker_policy_chips');
            if (!root) return;
            root.innerHTML = (Array.isArray(chips) ? chips : []).map((chip) => {
                const ok = !!chip.ok;
                const label = String(chip.label || 'policy');
                const detail = String(chip.detail || '');
                const bg = ok ? 'rgba(69, 172, 97, 0.15)' : 'rgba(200, 70, 70, 0.2)';
                const fg = ok ? '#7ee2a0' : '#ff8f8f';
                return `<span class="pill" title="${htmlEscape(detail)}" style="border-color:${fg}; color:${fg}; background:${bg};">${ok ? 'PASS' : 'BLOCK'}: ${htmlEscape(label)}</span>`;
            }).join('');
        }

        function syncAdvancedPolicyAwareness() {
            const classEl = document.getElementById('maker_agent_class');
            const typeEl = document.getElementById('maker_agent_type');
            const rankEl = document.getElementById('maker_rank');
            const command = document.getElementById('skill_command');
            const travel = document.getElementById('skill_bossgate_travel_control');
            const scope = document.getElementById('maker_dispatch_scope');
            const autonomous = document.getElementById('maker_dispatch_autonomous');
            const remoteHunt = document.getElementById('maker_dispatch_remote_hunt');
            const leaveNoCmd = document.getElementById('maker_dispatch_leave_without_command');
            const lanWhenIdle = document.getElementById('maker_dispatch_lan_when_idle');
            const validation = document.getElementById('maker_validation');
            if (!classEl || !typeEl || !rankEl || !command || !travel || !scope || !autonomous || !remoteHunt || !leaveNoCmd || !lanWhenIdle) return;

            const agentClass = (classEl.value || '').trim();
            const type = (typeEl.value || '').trim();
            const personalityPreset = (document.getElementById('maker_personality')?.value || 'balanced').trim().toLowerCase();
            const behaviorPatterns = selectedBehaviorPatterns('maker_behavior_patterns');
            const personalityInterests = parseCsvTags(document.getElementById('maker_personality_interests')?.value || '');
            const localRangerMode = personalityPreset === 'introvert_local' || behaviorPatterns.includes('ranger_local');
            const notes = [];
            const chips = [];

            command.disabled = false;
            travel.disabled = false;
            scope.disabled = false;
            remoteHunt.disabled = false;
            leaveNoCmd.disabled = false;
            lanWhenIdle.disabled = false;

            const sigilIds = [
                'sigil_sigil_transporter',
                'sigil_prime_overwatch',
                'sigil_sigil_bind',
                'sigil_sigil_trace',
                'sigil_sigil_harmony',
                'sigil_prime_foresight',
                'sigil_prime_bastion',
                'sigil_sigil_palette',
                'sigil_sigil_resonance',
                'sigil_sigil_flux',
                'sigil_sigil_anchor',
                'sigil_sigil_lens',
                'sigil_sigil_weave',
                'sigil_sigil_echo',
                'sigil_sigil_guard',
                'sigil_sigil_spark',
                'sigil_sigil_patch',
                'sigil_sigil_scribe',
                'sigil_sigil_orbit',
                'sigil_sigil_shield',
            ];
            const transporter = document.getElementById('sigil_sigil_transporter');
            for (const id of sigilIds) {
                const el = document.getElementById(id);
                if (!el) continue;
                if (agentClass === 'prime') {
                    el.disabled = false;
                } else if (agentClass === 'skilled') {
                    const isTransporter = id === 'sigil_sigil_transporter';
                    el.disabled = !isTransporter;
                    if (!isTransporter) el.checked = false;
                } else {
                    el.disabled = true;
                    el.checked = false;
                }
            }
            if (agentClass === 'normalized') {
                notes.push('normalized class: sigils disabled');
            }
            if (agentClass === 'skilled') {
                notes.push('skilled class: optional sigil specialist path allows only sigil_transporter');
                chips.push({ ok: !selectedAdvancedSigils().some((s) => s !== 'sigil_transporter'), label: 'skilled sigil allowlist', detail: 'skilled sigil path only allows sigil_transporter' });
            }

            if (type === 'authority') {
                command.checked = true;
                command.disabled = true;
                travel.checked = false;
                travel.disabled = true;
                notes.push('authority: command required, travel-control disallowed');
                chips.push({ ok: command.checked === true, label: 'authority requires command', detail: 'authority agents must keep command enabled' });
                chips.push({ ok: travel.checked === false, label: 'authority blocks travel-control', detail: 'authority agents cannot use bossgate_travel_control' });
            } else if (type === 'controller') {
                command.checked = true;
                command.disabled = true;
                autonomous.checked = true;
                autonomous.disabled = true;
                remoteHunt.checked = false;
                remoteHunt.disabled = true;
                leaveNoCmd.checked = false;
                leaveNoCmd.disabled = true;
                lanWhenIdle.checked = true;
                lanWhenIdle.disabled = true;
                if (scope.value === 'remote') scope.value = 'host';
                notes.push('controller: local-first, remote only when directed');
                chips.push({ ok: command.checked === true, label: 'controller requires command', detail: 'controller agents must keep command enabled' });
                chips.push({ ok: remoteHunt.checked === false, label: 'controller no proactive remote hunt', detail: 'controller agents should not proactively hunt remote work' });
                chips.push({ ok: leaveNoCmd.checked === false, label: 'controller cannot leave host without command', detail: 'controller remote movement requires direction' });
                chips.push({ ok: scope.value === 'host' || scope.value === 'lan', label: 'controller scope host/lan', detail: 'controller preferred scope must be host or lan' });
            } else if (type === 'ranger') {
                command.checked = false;
                command.disabled = true;
                travel.checked = true;
                travel.disabled = true;
                autonomous.checked = true;
                autonomous.disabled = true;
                remoteHunt.checked = !localRangerMode;
                remoteHunt.disabled = true;
                leaveNoCmd.checked = !localRangerMode;
                leaveNoCmd.disabled = true;
                lanWhenIdle.checked = true;
                lanWhenIdle.disabled = false;
                scope.value = localRangerMode ? (scope.value === 'lan' ? 'lan' : 'host') : 'remote';
                scope.disabled = true;
                notes.push(localRangerMode
                    ? 'ranger: local quiet-ranger behavior locked (host/lan proactive)'
                    : 'ranger: autonomous remote fixer behavior locked');
                chips.push({ ok: command.checked === false, label: 'ranger blocks command', detail: 'ranger agents cannot include command skill' });
                chips.push({ ok: travel.checked === true, label: 'ranger requires travel-control', detail: 'ranger agents must include bossgate_travel_control' });
                chips.push({ ok: localRangerMode ? remoteHunt.checked === false : remoteHunt.checked === true, label: 'ranger hunt profile', detail: localRangerMode ? 'local quiet-ranger disables proactive remote hunt' : 'ranger agents should actively hunt remote repair work' });
                chips.push({ ok: localRangerMode ? (scope.value === 'host' || scope.value === 'lan') : scope.value === 'remote', label: 'ranger scope profile', detail: localRangerMode ? 'local quiet-ranger scope must be host/lan' : 'ranger preferred scope must be remote' });
            } else if (type === 'worker') {
                command.checked = false;
                command.disabled = true;
                notes.push('worker: command skill disallowed');
                chips.push({ ok: command.checked === false, label: 'worker blocks command', detail: 'worker agents cannot include command' });
            } else if (type === 'security') {
                travel.checked = false;
                travel.disabled = true;
                notes.push('security: travel-control disallowed');
                chips.push({ ok: travel.checked === false, label: 'security blocks travel-control', detail: 'security agents cannot include bossgate_travel_control' });
            } else if (type === 'tester') {
                command.checked = false;
                command.disabled = true;
                notes.push('tester: command skill disallowed');
                chips.push({ ok: command.checked === false, label: 'tester blocks command', detail: 'tester agents cannot include command' });
            }

            const rankOrder = ['cadet', 'specialist', 'lieutenant', 'captain', 'commander', 'general', 'admiral'];
            const needsCaptain = command.checked;
            if (needsCaptain && rankOrder.indexOf(rankEl.value) < rankOrder.indexOf('captain')) {
                rankEl.value = 'captain';
                notes.push('rank auto-adjusted to captain because command is enabled');
            }
            chips.push({ ok: !needsCaptain || rankOrder.indexOf(rankEl.value) >= rankOrder.indexOf('captain'), label: 'command rank gate', detail: 'command requires rank captain or above' });
            for (const option of Array.from(rankEl.options || [])) {
                if (needsCaptain && rankOrder.indexOf(option.value) < rankOrder.indexOf('captain')) {
                    option.disabled = true;
                } else {
                    option.disabled = false;
                }
            }

            if (agentClass === 'prime') {
                const hasSigil = selectedAdvancedSigils().length > 0 || parseCsvTags(document.getElementById('maker_custom_sigils').value || '').length > 0;
                chips.push({ ok: hasSigil, label: 'prime sigil requirement', detail: 'prime agents should define at least one sigil' });
            }

            chips.push({ ok: true, label: `personality wrapper (${personalityPreset})`, detail: 'behavioral wrapper shapes decision style and claim protocol' });
            chips.push({ ok: true, label: `behavior overlays (${behaviorPatterns.length})`, detail: behaviorPatterns.length ? behaviorPatterns.join(', ') : 'none' });
            chips.push({ ok: true, label: `interest affinities (${personalityInterests.length})`, detail: personalityInterests.length ? personalityInterests.join(', ') : 'none' });

            const caps = rankCaps(rankEl.value);
            const selectedSkillsCount = selectedAdvancedSkills().length + parseCsvTags(document.getElementById('maker_custom_skills').value || '').length;
            const selectedSigils = selectedAdvancedSigils();
            const selectedSigilsCount = selectedSigils.length + parseCsvTags(document.getElementById('maker_custom_sigils').value || '').length;
            chips.push({ ok: selectedSkillsCount <= caps.skills, label: `rank skills cap (${caps.skills})`, detail: `selected skills: ${selectedSkillsCount}` });
            chips.push({ ok: selectedSigilsCount <= caps.sigils, label: `rank sigils cap (${caps.sigils})`, detail: `selected sigils: ${selectedSigilsCount}` });
            chips.push({ ok: true, label: `rank MCP cap (${caps.mcp})`, detail: 'MCP server count is enforced during runtime profile validation' });

            if (agentClass === 'prime') {
                chips.push({ ok: true, label: 'prime leadership optional', detail: 'leadership is determined by command + rank, not by prime class' });
            }

            if (agentClass === 'skilled') {
                const hasSkills = selectedSkillsCount > 0;
                const hasSigils = selectedSigilsCount > 0;
                chips.push({ ok: hasSkills !== hasSigils, label: 'skilled dual-path rule', detail: 'choose skills path OR one-sigil path' });
                if (hasSigils) {
                    chips.push({ ok: selectedSigilsCount === 1, label: 'skilled sigil count', detail: 'skilled sigil path requires exactly one sigil' });
                    chips.push({ ok: selectedSigils.every((s) => s === 'sigil_transporter'), label: 'skilled transporter sigil', detail: 'skilled sigil path only permits sigil_transporter' });
                }
            }

            setMakerPolicyChips(chips);

            if (validation) {
                validation.textContent = notes.length
                    ? ('Policy locks: ' + notes.join(' | '))
                    : 'Role-aware validation ready.';
            }
        }

        function buildWizardDraft() {
            const name = (document.getElementById('wizard_name').value || '').trim();
            const endpoint = (document.getElementById('wizard_endpoint').value || '').trim();
            const roleFocus = (document.getElementById('wizard_role_focus').value || '').trim();
            const scope = (document.getElementById('wizard_scope').value || 'host').trim();
            const behavior = (document.getElementById('wizard_behavior').value || 'directive_local').trim();
            const power = (document.getElementById('wizard_power').value || 'skilled').trim();
            const wizardPersonality = (document.getElementById('wizard_personality').value || 'balanced').trim();
            const wizardPersonalityNotes = (document.getElementById('wizard_personality_notes').value || '').trim();
            const wizardInterests = parseCsvTags(document.getElementById('wizard_personality_interests').value || '');
            const wizardBehaviorPatterns = selectedBehaviorPatterns('wizard_behavior_patterns');
            const encrypt = !!document.getElementById('wizard_encrypt_profile').checked;
            const wizardSkills = selectedWizardValues('wizard_skill_list');
            const wizardSigils = selectedWizardValues('wizard_sigil_list');
            const wizardStateMachineTemplate = (document.getElementById('wizard_state_machine_template').value || 'none').trim();
            const wizardIconPath = (document.getElementById('wizard_icon_path').value || '').trim();

            document.getElementById('maker_name').value = name;
            if (endpoint) document.getElementById('maker_endpoint').value = endpoint;
            document.getElementById('maker_agent_class').value = power;
            document.getElementById('maker_encrypt_profile').checked = encrypt;
            document.getElementById('maker_bossgate_enabled').checked = encrypt;
            document.getElementById('maker_personality').value = wizardPersonality;
            document.getElementById('maker_personality_notes').value = wizardPersonalityNotes;
            document.getElementById('maker_personality_interests').value = wizardInterests.join(', ');
            const makerBehaviorPatterns = document.getElementById('maker_behavior_patterns');
            if (makerBehaviorPatterns) {
                const selected = new Set(wizardBehaviorPatterns);
                if (wizardPersonality.toLowerCase() === 'introvert_local') selected.add('ranger_local');
                for (const option of Array.from(makerBehaviorPatterns.options || [])) {
                    option.selected = selected.has(String(option.value || '').trim().toLowerCase());
                }
            }

            if (behavior === 'proactive_remote') {
                document.getElementById('maker_agent_type').value = 'ranger';
                document.getElementById('maker_rank').value = 'lieutenant';
                document.getElementById('skill_command').checked = false;
                document.getElementById('skill_bossgate_travel_control').checked = true;
                document.getElementById('maker_dispatch_scope').value = 'remote';
            } else if (behavior === 'security_guard') {
                document.getElementById('maker_agent_type').value = 'security';
                document.getElementById('maker_rank').value = 'specialist';
                document.getElementById('skill_command').checked = false;
                document.getElementById('skill_bossgate_travel_control').checked = false;
                document.getElementById('maker_dispatch_scope').value = scope === 'remote' ? 'lan' : scope;
            } else if (behavior === 'qa_tester') {
                document.getElementById('maker_agent_type').value = 'tester';
                document.getElementById('maker_rank').value = 'specialist';
                document.getElementById('skill_command').checked = false;
                document.getElementById('skill_bossgate_travel_control').checked = false;
                document.getElementById('maker_dispatch_scope').value = scope === 'remote' ? 'lan' : scope;
            } else {
                if (power === 'prime') {
                    document.getElementById('maker_agent_type').value = 'worker';
                    document.getElementById('maker_rank').value = 'lieutenant';
                    document.getElementById('skill_command').checked = false;
                    document.getElementById('skill_bossgate_travel_control').checked = false;
                    document.getElementById('maker_dispatch_scope').value = (scope === 'remote') ? 'lan' : scope;
                } else {
                    document.getElementById('maker_agent_type').value = 'controller';
                    document.getElementById('maker_rank').value = 'captain';
                    document.getElementById('skill_command').checked = true;
                    document.getElementById('skill_bossgate_travel_control').checked = (scope !== 'host');
                    document.getElementById('maker_dispatch_scope').value = (scope === 'remote') ? 'lan' : scope;
                }
            }

            const baseSystemText = roleFocus
                ? (`You are ${name || 'a specialist agent'}. Mission: ${roleFocus}.`) 
                : 'You are a helpful specialist agent.';
            document.getElementById('maker_system').value = baseSystemText;
            document.getElementById('maker_custom_skills').value = wizardSkills.join(', ');
            document.getElementById('maker_custom_sigils').value = (power === 'prime') ? wizardSigils.join(', ') : '';
            const makerStateMachineTemplate = document.getElementById('maker_state_machine_template');
            if (makerStateMachineTemplate) {
                makerStateMachineTemplate.value = wizardStateMachineTemplate;
                applySelectedStateMachineTemplate();
            }
            document.getElementById('maker_icon_path').value = wizardIconPath;
            const makerIconMode = document.getElementById('maker_icon_mode');
            if (makerIconMode) makerIconMode.value = wizardIconPath ? 'upload' : 'none';
            switchAgentForgeMode('advanced');
            toggleMakerIconSource();
            syncAdvancedPolicyAwareness();
        }

        async function createWizardAgent() {
            buildWizardDraft();
            await createAgentProfile();
        }

        function renderChat() {
            const root = document.getElementById('chat_log');
            if (!root) return;
            if (!chatHistory.length) {
                root.textContent = 'No messages yet.';
                return;
            }
            root.textContent = chatHistory.map((m) => `${m.role.toUpperCase()} (${m.endpoint}): ${m.content}`).join('\\n\\n');
        }

        async function sendChat() {
            const endpoint = (document.getElementById('chat_endpoint').value || '').trim();
            const system = (document.getElementById('chat_system').value || '').trim();
            const prompt = (document.getElementById('chat_prompt').value || '').trim();
            if (!endpoint || !prompt) {
                alert('endpoint and prompt are required');
                return;
            }
            chatHistory.push({ role: 'user', endpoint, content: prompt });
            renderChat();
            document.getElementById('chat_prompt').value = '';
            const res = await fetch('/api/model/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ endpoint, system, prompt })
            });
            const data = await res.json();
            chatHistory.push({ role: 'assistant', endpoint, content: data.text || data.message || JSON.stringify(data) });
            renderChat();
        }

        async function refreshAgentMaker() {
            const data = await fetchJsonWithTimeout('/api/model/agents');
            const agents = (data && data.agents && typeof data.agents === 'object') ? data.agents : {};
            const names = Object.keys(agents);
            document.getElementById('maker_agents').textContent = names.length ? JSON.stringify(agents, null, 2) : 'No agents defined.';
            const sel = document.getElementById('maker_agent_select');
            if (sel) {
                const current = sel.value;
                sel.innerHTML = names.map((n) => `<option value="${n}">${n}</option>`).join('');
                if (current && names.includes(current)) sel.value = current;
            }
            await inspectSelectedAgentProfile();
            syncAdvancedPolicyAwareness();
        }

        function renderSelectedAgentProfile(data) {
            const policyRoot = document.getElementById('maker_agent_policy');
            const badge = document.getElementById('maker_agent_policy_badge');
            const detail = document.getElementById('maker_agent_view');
            const summaryTitle = document.getElementById('maker_agent_summary_title');
            const summarySubtitle = document.getElementById('maker_agent_summary_subtitle');
            const summaryChips = document.getElementById('maker_agent_summary_chips');
            const summaryGrid = document.getElementById('maker_agent_summary_grid');
            if (!policyRoot || !badge || !detail || !summaryTitle || !summarySubtitle || !summaryChips || !summaryGrid) return;

            function chip(label, color) {
                return `<span style="display:inline-flex; align-items:center; padding:5px 10px; border-radius:999px; border:1px solid ${color}; color:${color}; font-size:12px; letter-spacing:0.02em;">${label}</span>`;
            }

            function gridItem(label, value) {
                return `<div style="border:1px solid #243042; border-radius:10px; padding:8px 10px; background:rgba(10,14,20,0.72);">
                    <div style="font-size:11px; color:#8ea0b8; text-transform:uppercase; letter-spacing:0.08em; margin-bottom:4px;">${label}</div>
                    <div style="font-size:13px; color:#e5eefc; word-break:break-word;">${value || 'n/a'}</div>
                </div>`;
            }

            if (!data || !data.ok) {
                badge.textContent = 'Unavailable';
                badge.style.borderColor = '#7f1d1d';
                badge.style.color = '#fca5a5';
                policyRoot.textContent = (data && data.message) ? String(data.message) : 'Unable to inspect agent profile.';
                summaryTitle.textContent = 'Inspection unavailable';
                summarySubtitle.textContent = 'The forge could not retrieve a readable profile payload.';
                summaryChips.innerHTML = chip('inspection failed', '#fca5a5');
                summaryGrid.innerHTML = gridItem('Status', 'Unavailable');
                detail.textContent = JSON.stringify(data || { ok: false, message: 'No response returned.' }, null, 2);
                return;
            }

            if (data.sealed) {
                const identity = (data.public_identity_card && typeof data.public_identity_card === 'object') ? data.public_identity_card : {};
                const modelCard = (data.model_card && typeof data.model_card === 'object') ? data.model_card : {};
                badge.textContent = 'Sealed Asset';
                badge.style.borderColor = '#7c3aed';
                badge.style.color = '#c4b5fd';
                const policy = String(data.view_policy || 'model_card_only_outside_origin_forge').replaceAll('_', ' ');
                const message = String(data.message || 'Model card only.');
                policyRoot.textContent = `${message} Policy: ${policy}.`;
                summaryTitle.textContent = `${String(data.agent || identity.name || 'Unknown Agent')} is sealed`;
                summarySubtitle.textContent = 'This package is armored outside its forge of creation. Only its public identity and model card are exposed here.';
                summaryChips.innerHTML = [
                    chip('sealed package', '#c4b5fd'),
                    chip(`posture: ${String(data.disclosure_posture || 'hidden')}`, '#93c5fd'),
                    chip('model card visible', '#67e8f9'),
                ].join('');
                summaryGrid.innerHTML = [
                    gridItem('Public Name', String(identity.name || data.agent || 'n/a')),
                    gridItem('Public ID', String(identity.public_id || data.agent || 'n/a')),
                    gridItem('Class', String(identity.agent_class || modelCard.agent_class || 'n/a')),
                    gridItem('Type', String(identity.agent_type || modelCard.agent_type || 'n/a')),
                    gridItem('Rank', String(identity.rank || modelCard.rank || 'n/a')),
                    gridItem('Origin Forge View', data.full_view_available_at_origin_forge ? 'Available at creation forge' : 'Not advertised'),
                ].join('');
                detail.textContent = JSON.stringify({
                    agent: data.agent,
                    disclosure_posture: data.disclosure_posture,
                    full_view_available_at_origin_forge: !!data.full_view_available_at_origin_forge,
                    public_identity_card: data.public_identity_card || {},
                    model_card: data.model_card || {},
                }, null, 2);
                return;
            }

            badge.textContent = 'Origin Forge View';
            badge.style.borderColor = '#14532d';
            badge.style.color = '#86efac';
            policyRoot.textContent = 'Authenticated origin-forge access granted. Full profile view is available on this forge.';
            const profile = (data.profile && typeof data.profile === 'object') ? data.profile : {};
            summaryTitle.textContent = `${String(data.agent || profile.name || 'Selected agent')} opened on origin forge`;
            summarySubtitle.textContent = 'This forge created the package and is allowed to view beyond the public armor.';
            summaryChips.innerHTML = [
                chip('origin forge access', '#86efac'),
                chip(`posture: ${String(data.disclosure_posture || 'non_hidden')}`, '#93c5fd'),
                chip('full profile visible', '#fcd34d'),
            ].join('');
            summaryGrid.innerHTML = [
                gridItem('Name', String(profile.name || data.agent || 'n/a')),
                gridItem('Endpoint', String(profile.endpoint || 'n/a')),
                gridItem('Class', String(profile.agent_class || 'n/a')),
                gridItem('Type', String(profile.agent_type || 'n/a')),
                gridItem('Rank', String(profile.rank || 'n/a')),
                gridItem('BossGate Enabled', profile.bossgate_enabled ? 'Yes' : 'No'),
            ].join('');
            detail.textContent = JSON.stringify(data.profile || data, null, 2);
        }

        async function inspectSelectedAgentProfile() {
            const sel = document.getElementById('maker_agent_select');
            const detail = document.getElementById('maker_agent_view');
            const policyRoot = document.getElementById('maker_agent_policy');
            const badge = document.getElementById('maker_agent_policy_badge');
            const name = (sel && sel.value) ? String(sel.value).trim() : '';
            if (!detail || !policyRoot || !badge) return;
            if (!name) {
                badge.textContent = 'Awaiting selection';
                badge.style.borderColor = '#4b5563';
                badge.style.color = '#cbd5e1';
                policyRoot.textContent = 'Select an agent to inspect its sealed status or authenticated forge view.';
                const summaryTitle = document.getElementById('maker_agent_summary_title');
                const summarySubtitle = document.getElementById('maker_agent_summary_subtitle');
                const summaryChips = document.getElementById('maker_agent_summary_chips');
                const summaryGrid = document.getElementById('maker_agent_summary_grid');
                if (summaryTitle) summaryTitle.textContent = 'No agent selected';
                if (summarySubtitle) summarySubtitle.textContent = 'Choose an agent to reveal its package status.';
                if (summaryChips) summaryChips.innerHTML = '';
                if (summaryGrid) summaryGrid.innerHTML = '';
                detail.textContent = 'No agent selected.';
                return;
            }
            policyRoot.textContent = `Inspecting ${name}...`;
            detail.textContent = 'Loading agent view...';
            const data = await fetchJsonWithTimeout(`/api/agentforge/agents/${encodeURIComponent(name)}/view?viewer_id=control-hall&viewer_channel=bossforgeos`);
            renderSelectedAgentProfile(data);
        }

        async function createAgentProfile() {
            const temperatureValue = parseFloat(document.getElementById('maker_temperature').value || '0.2');
            const maxTokensValue = parseInt(document.getElementById('maker_max_tokens').value || '900', 10);
            const mergedSkills = Array.from(new Set([
                ...selectedAdvancedSkills(),
                ...parseCsvTags(document.getElementById('maker_custom_skills').value || ''),
            ])).sort();
            const mergedSigils = Array.from(new Set([
                ...selectedAdvancedSigils(),
                ...parseCsvTags(document.getElementById('maker_custom_sigils').value || ''),
            ])).sort();
            const rankValue = (document.getElementById('maker_rank').value || '').trim();
            const personalityPreset = (document.getElementById('maker_personality').value || 'balanced').trim().toLowerCase();
            const personalityNotes = (document.getElementById('maker_personality_notes').value || '').trim();
            const personalityInterests = parseCsvTags(document.getElementById('maker_personality_interests').value || '');
            const behaviorPatterns = selectedBehaviorPatterns('maker_behavior_patterns');
            if (personalityPreset === 'introvert_local' && !behaviorPatterns.includes('ranger_local')) {
                behaviorPatterns.push('ranger_local');
            }
            const cap = rankCaps(rankValue);
            if (mergedSkills.length > cap.skills) {
                alert(`rank ${rankValue} allows at most ${cap.skills} skills`);
                return;
            }
            if (mergedSigils.length > cap.sigils) {
                alert(`rank ${rankValue} allows at most ${cap.sigils} sigils`);
                return;
            }
            let stateMachine = null;
            try {
                stateMachine = parseAdvancedStateMachine();
            } catch {
                return;
            }
            const payload = {
                name: (document.getElementById('maker_name').value || '').trim(),
                endpoint: (document.getElementById('maker_endpoint').value || '').trim(),
                system: composeSystemWithPersonality((document.getElementById('maker_system').value || '').trim(), personalityPreset, personalityNotes),
                temperature: Number.isFinite(temperatureValue) ? temperatureValue : 0.2,
                max_tokens: Number.isFinite(maxTokensValue) ? maxTokensValue : 900,
                agent_class: (document.getElementById('maker_agent_class').value || '').trim(),
                agent_type: (document.getElementById('maker_agent_type').value || '').trim(),
                rank: rankValue,
                skills: mergedSkills,
                sigils: mergedSigils,
                personality_wrapper: {
                    preset: personalityPreset,
                    notes: personalityNotes,
                    behavior_patterns: behaviorPatterns,
                    interests: personalityInterests,
                },
                system_wrapper: {
                    enabled: true,
                    name: 'personality_wrapper',
                    mode: personalityPreset,
                    entrypoint: 'agentforge_personality_v1',
                    contract_version: '1.0',
                },
                instructions: {
                    system: composeSystemWithPersonality((document.getElementById('maker_system').value || '').trim(), personalityPreset, personalityNotes),
                    developer: personalityNotes,
                },
                state_machine: stateMachine,
                custom_icon_path: (document.getElementById('maker_icon_path').value || '').trim(),
                has_llm: !!document.getElementById('maker_has_llm').checked,
                bossgate_enabled: !!document.getElementById('maker_bossgate_enabled').checked,
                encrypt_profile: !!document.getElementById('maker_encrypt_profile').checked,
                model_source_path: (document.getElementById('maker_model_source_path').value || '').trim(),
                model_base_source_path: (document.getElementById('maker_model_base_source_path').value || '').trim(),
                dispatch_policy: {
                    autonomous_bus_intake: !!document.getElementById('maker_dispatch_autonomous').checked,
                    proactive_remote_hunt: !!document.getElementById('maker_dispatch_remote_hunt').checked,
                    preferred_scope: (document.getElementById('maker_dispatch_scope').value || 'host').trim(),
                    can_leave_host_without_command: !!document.getElementById('maker_dispatch_leave_without_command').checked,
                    can_leave_host_for_lan_when_host_idle: !!document.getElementById('maker_dispatch_lan_when_idle').checked,
                },
            };
            if (!payload.name || !payload.endpoint) {
                alert('name and endpoint are required');
                return;
            }
            if (payload.has_llm && !payload.model_source_path) {
                alert('a complete local model source directory is required for LLM-enabled agents');
                return;
            }
            const res = await fetch('/api/model/agents/create', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            document.getElementById('maker_result').textContent = JSON.stringify(data, null, 2);
            await refreshAgentMaker();
        }

        async function runIncidentTriage() {
            const title = (document.getElementById('triage_title').value || '').trim();
            const summary = (document.getElementById('triage_summary').value || '').trim();
            const scope = (document.getElementById('triage_scope').value || '').trim();
            const urgency = parseFloat(document.getElementById('triage_urgency').value || '0.55');
            const risk = parseFloat(document.getElementById('triage_risk').value || '0.50');
            const proximity = parseFloat(document.getElementById('triage_proximity').value || '0.70');
            const confidence = parseFloat(document.getElementById('triage_confidence').value || '0.60');
            const commanded = !!document.getElementById('triage_commanded').checked;
            const incident = {
                title,
                summary,
                scope,
                urgency,
                risk,
                proximity,
                confidence,
                commanded,
            };
            const res = await fetch('/api/model/agents/triage', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ incident }),
            });
            const data = await res.json();
            document.getElementById('triage_result').textContent = JSON.stringify(data, null, 2);
        }

        async function runAgentProfile() {
            const payload = {
                name: (document.getElementById('maker_agent_select').value || '').trim(),
                task: (document.getElementById('maker_task').value || '').trim(),
                endpoint: (document.getElementById('maker_override_endpoint').value || '').trim(),
                memory_context: {
                    user: (document.getElementById('maker_user').value || '').trim(),
                    employer: (document.getElementById('maker_employer').value || '').trim(),
                    project: (document.getElementById('maker_project').value || '').trim(),
                    counterpart_agent: (document.getElementById('maker_counterpart').value || '').trim(),
                },
            };
            if (!payload.name || !payload.task) {
                alert('name and task are required');
                return;
            }
            const res = await fetch('/api/model/agents/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            document.getElementById('maker_result').textContent = JSON.stringify(data, null, 2);
        }

        async function deleteAgentProfile() {
            const payload = { name: (document.getElementById('maker_agent_select').value || '').trim() };
            if (!payload.name) {
                alert('select an agent first');
                return;
            }
            const res = await fetch('/api/model/agents/delete', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            document.getElementById('maker_result').textContent = JSON.stringify(data, null, 2);
            await refreshAgentMaker();
        }

        async function refreshSecurityState() {
            const data = await fetchJsonWithTimeout('/api/security/state');
            document.getElementById('security_findings').textContent = JSON.stringify(data, null, 2);
        }

        async function runSecurityScan() {
            const path = (document.getElementById('security_scan_path').value || '').trim();
            const res = await fetch('/api/security/scan', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path }) });
            const data = await res.json();
            document.getElementById('security_findings').textContent = JSON.stringify(data, null, 2);
        }

        async function refreshSecretsList() {
            const data = await fetchJsonWithTimeout('/api/security/secrets');
            document.getElementById('security_secrets').textContent = JSON.stringify(data, null, 2);
        }

        function sendManual() {
            const target = (document.getElementById('target').value || '').trim();
            const command = (document.getElementById('command').value || '').trim();
            if (!target || !command) {
                alert('target and command are required');
                return;
            }
            let args = {};
            try {
                args = JSON.parse(document.getElementById('args').value || '{}');
            } catch {
                alert('args must be valid JSON');
                return;
            }
            sendCmd(target, command, args);
        }

        function renderAgents(agentState) {
            const root = document.getElementById('agents');
            if (!root) return;
            const entries = Object.entries(agentState || {}).map(([name, info]) => {
                const klass = (info && info.health) || 'offline';
                const seen = (info && info.last_seen) || 'never';
                return '<div class="agent-item"><strong>' + name + '</strong><span class="pill ' + klass + '">' + klass + '</span><div class="muted">' + seen + '</div></div>';
            }).join('');
            root.innerHTML = entries || '<div class="muted">No agents found.</div>';
        }

        function taskStatusPillClass(status) {
            const key = String(status || '').trim().toLowerCase();
            if (key === 'done') return 'online';
            if (key === 'in_progress') return 'warning';
            if (key === 'blocked') return 'critical';
            return 'stale';
        }

        function taskStatusLabel(status) {
            const key = String(status || '').trim().toLowerCase();
            if (key === 'in_progress') return 'in progress';
            return key || 'assigned';
        }

        function renderAgentTaskTracker(data) {
            const root = document.getElementById('agent_task_tracker');
            if (!root) return;
            const items = (data && Array.isArray(data.items)) ? data.items : [];
            if (!items.length) {
                root.innerHTML = '<div class="agent-item"><strong>No tracked tasks</strong><div class="muted">Create assignments in AGENT_TASK_ASSIGNMENTS.md to bootstrap.</div></div>';
                return;
            }

            root.innerHTML = items.map((item) => {
                const taskId = htmlEscape(String(item.id || ''));
                const agent = htmlEscape(String(item.agent || 'unknown-agent'));
                const task = htmlEscape(String(item.task || ''));
                const status = String(item.status || 'assigned').toLowerCase();
                const statusLabel = htmlEscape(taskStatusLabel(status));
                const statusClass = taskStatusPillClass(status);
                const startedAt = htmlEscape(String(item.started_at || 'not started'));
                const completedAt = htmlEscape(String(item.completed_at || 'not completed'));
                const updatedAt = htmlEscape(String(item.updated_at || 'unknown'));
                const note = String(item.note || '').trim();
                const noteHtml = note ? ('<div class="agent-task-meta">note: ' + htmlEscape(note) + '</div>') : '';
                return '<div class="agent-task-card">'
                    + '<div class="agent-task-head"><span class="agent-task-agent">' + agent + '</span><span class="pill ' + statusClass + '">' + statusLabel + '</span></div>'
                    + '<div class="agent-task-text">' + task + '</div>'
                    + '<div class="agent-task-meta">started: ' + startedAt + ' | completed: ' + completedAt + '</div>'
                    + '<div class="agent-task-meta">updated: ' + updatedAt + '</div>'
                    + noteHtml
                    + '<div class="agent-task-actions">'
                    + '<button onclick="updateAgentTaskStatus(\\'' + taskId + '\\', \\'assigned\\')">Assign</button>'
                    + '<button onclick="updateAgentTaskStatus(\\'' + taskId + '\\', \\'in_progress\\')">Start</button>'
                    + '<button onclick="updateAgentTaskStatus(\\'' + taskId + '\\', \\'blocked\\')">Block</button>'
                    + '<button onclick="updateAgentTaskStatus(\\'' + taskId + '\\', \\'done\\')">Done</button>'
                    + '</div>'
                    + '</div>';
            }).join('');
        }

        async function refreshAgentTaskTracker() {
            const data = await fetchJsonWithTimeout('/api/agent_tasks', 5000);
            renderAgentTaskTracker(data);
        }

        async function updateAgentTaskStatus(taskId, status) {
            const note = status === 'blocked' ? (prompt('Blocked reason (optional):') || '').trim() : '';
            const res = await fetch('/api/agent_tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ task_id: taskId, status, note }),
            });
            const data = await res.json();
            renderAgentTaskTracker(data);
            const toast = document.getElementById('toast');
            if (toast) {
                toast.textContent = (data && data.ok) ? 'Task updated.' : ('Task update failed: ' + String(data?.message || 'unknown error'));
            }
        }

        function gaugeTone(percent) {
            const safe = Number.isFinite(percent) ? percent : 0;
            if (safe >= 90) return '#39ff14';
            if (safe >= 75) return '#5dff68';
            return '#00f5a0';
        }

        function percentValue(value) {
            const n = Number(value);
            if (!Number.isFinite(n)) return 0;
            return Math.max(0, Math.min(100, n));
        }

        function pulseClass(percent) {
            const p = percentValue(percent);
            if (p >= 85) return ' pulse-high';
            if (p >= 65) return ' pulse-mid';
            return '';
        }

        function computeDiskIoRates(disks) {
            const nowTs = Date.now() / 1000;
            const elapsed = snapshotDiskIoLastTs > 0 ? Math.max(0, nowTs - snapshotDiskIoLastTs) : 0;
            const current = {};
            const rates = {};

            (Array.isArray(disks) ? disks : []).forEach((disk) => {
                const key = String(disk?.key || disk?.mount || disk?.device || '').trim();
                if (!key) return;
                const readBytes = Number(disk?.read_bytes);
                const writeBytes = Number(disk?.write_bytes);
                const hasRead = Number.isFinite(readBytes) && readBytes >= 0;
                const hasWrite = Number.isFinite(writeBytes) && writeBytes >= 0;
                current[key] = {
                    read_bytes: hasRead ? readBytes : null,
                    write_bytes: hasWrite ? writeBytes : null,
                };

                const prev = snapshotDiskIoLast[key];
                if (!prev || elapsed <= 0) {
                    rates[key] = { read_bps: 0, write_bps: 0 };
                    return;
                }

                const prevRead = Number(prev.read_bytes);
                const prevWrite = Number(prev.write_bytes);
                const readBps = (hasRead && Number.isFinite(prevRead) && readBytes >= prevRead)
                    ? (readBytes - prevRead) / elapsed
                    : 0;
                const writeBps = (hasWrite && Number.isFinite(prevWrite) && writeBytes >= prevWrite)
                    ? (writeBytes - prevWrite) / elapsed
                    : 0;

                rates[key] = {
                    read_bps: Math.max(0, readBps),
                    write_bps: Math.max(0, writeBps),
                };
            });

            snapshotDiskIoLast = current;
            snapshotDiskIoLastTs = nowTs;
            return rates;
        }

        function renderSnapshotDashboard(snapshot) {
            const root = document.getElementById('snapshot_dashboard');
            const warningsRoot = document.getElementById('snapshot_warnings');
            if (!root || !warningsRoot) return;

            const system = (snapshot && snapshot.system && typeof snapshot.system === 'object') ? snapshot.system : {};
            const memory = (system.memory && typeof system.memory === 'object') ? system.memory : {};
            const swap = (system.swap && typeof system.swap === 'object') ? system.swap : {};
            const disk = (snapshot && snapshot.disk && typeof snapshot.disk === 'object') ? snapshot.disk : {};
            const disks = (snapshot && Array.isArray(snapshot.disks)) ? snapshot.disks : [];
            const thermal = (snapshot && snapshot.thermal && typeof snapshot.thermal === 'object') ? snapshot.thermal : {};
            const fans = (snapshot && snapshot.fans && typeof snapshot.fans === 'object') ? snapshot.fans : {};
            const gpu = (snapshot && snapshot.gpu_vram && Array.isArray(snapshot.gpu_vram.gpus)) ? snapshot.gpu_vram.gpus[0] : null;

            const safeNumber = (value) => {
                const n = Number(value);
                return Number.isFinite(n) ? n : null;
            };

            const gauges = [
                {
                    label: 'CPU',
                    percent: percentValue(system.cpu_percent),
                    detail: String(Number.isFinite(Number(system.cpu_percent)) ? Number(system.cpu_percent).toFixed(1) : '0.0') + '%',
                    readPct: 0,
                    writePct: 0,
                },
                {
                    label: 'RAM',
                    percent: percentValue(memory.percent),
                    detail: (memory.used_gb ?? '?') + ' / ' + (memory.total_gb ?? '?') + ' GB',
                    readPct: 0,
                    writePct: 0,
                },
                {
                    label: 'Swap',
                    percent: percentValue(swap.percent),
                    detail: (swap.used_gb ?? '?') + ' / ' + (swap.total_gb ?? '?') + ' GB',
                    readPct: 0,
                    writePct: 0,
                },
            ];

            const diskRows = disks.length
                ? disks
                : [
                    {
                        key: String(disk.root || 'disk').toLowerCase(),
                        mount: String(disk.root || 'disk'),
                        percent: disk.percent,
                        used_gb: disk.used_gb,
                        total_gb: disk.total_gb,
                        read_bytes: null,
                        write_bytes: null,
                    },
                ];
            const ioRates = computeDiskIoRates(diskRows);
            const maxObservedRate = Math.max(
                50 * 1024 * 1024,
                ...Object.values(ioRates).map((r) => Math.max(Number(r?.read_bps || 0), Number(r?.write_bps || 0)))
            );

            diskRows.forEach((diskRow) => {
                const key = String(diskRow?.key || diskRow?.mount || '').trim().toLowerCase();
                const rates = ioRates[key] || { read_bps: 0, write_bps: 0 };
                const readMbps = Number(rates.read_bps || 0) / (1024 * 1024);
                const writeMbps = Number(rates.write_bps || 0) / (1024 * 1024);
                const mount = String(diskRow?.mount || diskRow?.device || diskRow?.key || 'disk');
                const readPct = percentValue((Number(rates.read_bps || 0) / maxObservedRate) * 100);
                const writePct = percentValue((Number(rates.write_bps || 0) / maxObservedRate) * 100);
                gauges.push({
                    label: 'Disk ' + mount,
                    percent: percentValue(diskRow?.percent),
                    detail: (diskRow?.used_gb ?? '?') + ' / ' + (diskRow?.total_gb ?? '?') + ' GB | R ' + readMbps.toFixed(1) + ' MB/s | W ' + writeMbps.toFixed(1) + ' MB/s',
                    readPct,
                    writePct,
                    multiLegend: true,
                });
            });

            if (gpu) {
                gauges.push({
                    label: 'GPU VRAM',
                    percent: percentValue(gpu.percent),
                    detail: (gpu.used_gb ?? '?') + ' / ' + (gpu.total_gb ?? '?') + ' GB',
                    readPct: 0,
                    writePct: 0,
                });
            }

            const cpuTemp = safeNumber(thermal.cpu_temp_c);
            const maxTemp = safeNumber(thermal.max_temp_c);
            const gpuTemp = safeNumber(gpu && gpu.temperature_c);
            const tempC = (cpuTemp !== null) ? cpuTemp : ((gpuTemp !== null) ? gpuTemp : maxTemp);
            if (tempC !== null) {
                const tempPct = Math.max(0, Math.min(100, (tempC / 100) * 100));
                const tempSource = (cpuTemp !== null) ? 'cpu' : ((gpuTemp !== null) ? 'gpu' : 'sensor');
                gauges.push({
                    label: 'Temp',
                    percent: percentValue(tempPct),
                    detail: tempC.toFixed(1) + ' C (' + tempSource + ')',
                    readPct: 0,
                    writePct: 0,
                });
            }

            const gpuFan = safeNumber(gpu && gpu.fan_percent);
            const maxFanRpm = safeNumber(fans.max_rpm);
            if (gpuFan !== null || maxFanRpm !== null) {
                const fanPercent = (gpuFan !== null)
                    ? percentValue(gpuFan)
                    : percentValue((Math.max(0, maxFanRpm) / 5000) * 100);
                const fanDetail = (gpuFan !== null)
                    ? (gpuFan.toFixed(1) + '% (gpu)')
                    : (Math.round(maxFanRpm || 0) + ' rpm');
                gauges.push({
                    label: 'Fan',
                    percent: fanPercent,
                    detail: fanDetail,
                    readPct: 0,
                    writePct: 0,
                });
            }

            root.innerHTML = gauges.map((item) => {
                const p = percentValue(item.percent);
                const tone = gaugeTone(p);
                const sweepClass = snapshotGaugeBooted ? '' : ' sweep';
                const pulse = pulseClass(p);
                const readPct = percentValue(item.readPct);
                const writePct = percentValue(item.writePct);
                const legend = item.multiLegend
                    ? '<div class="gauge-legend"><span class="gauge-legend-item"><span class="gauge-legend-line usage"></span>Usage</span><span class="gauge-legend-item"><span class="gauge-legend-line read"></span>Read</span><span class="gauge-legend-item"><span class="gauge-legend-line write"></span>Write</span></div>'
                    : '';
                return '<div class="gauge-card">'
                    + '<div class="gauge-head"><strong>' + htmlEscape(item.label) + '</strong><span class="muted">' + p.toFixed(1) + '%</span></div>'
                    + '<div class="tachometer' + sweepClass + pulse + '" style="--pct:' + p.toFixed(1) + ';--rdpct:' + readPct.toFixed(1) + ';--wrpct:' + writePct.toFixed(1) + ';--tone:' + tone + ';">'
                    + '<div class="halo"></div>'
                    + '<svg viewBox="0 0 100 60" aria-hidden="true">'
                    + '<path class="arc-bg" pathLength="100" d="M 10 50 A 40 40 0 0 1 90 50"></path>'
                    + '<path class="arc-fg" pathLength="100" d="M 10 50 A 40 40 0 0 1 90 50"></path>'
                    + '<path class="arc-rd" pathLength="100" d="M 10 50 A 40 40 0 0 1 90 50"></path>'
                    + '<path class="arc-wr" pathLength="100" d="M 10 50 A 40 40 0 0 1 90 50"></path>'
                    + '</svg>'
                    + '<div class="ticks"></div>'
                    + '</div>'
                        + legend
                    + '<div class="gauge-foot"><span>0%</span><span>' + htmlEscape(String(item.detail)) + '</span><span>100%</span></div>'
                    + '</div>';
            }).join('');
            snapshotGaugeBooted = true;

            const warnings = (snapshot && Array.isArray(snapshot.warnings)) ? snapshot.warnings : [];
            if (!warnings.length) {
                warningsRoot.innerHTML = '<li class="snapshot-warning-item good">No active pressure warnings</li>';
            } else {
                warningsRoot.innerHTML = warnings.map((w) => {
                    const text = String(w || 'warning');
                    const bad = text.toLowerCase().includes('critical') ? ' bad' : '';
                    return '<li class="snapshot-warning-item' + bad + '">' + htmlEscape(text) + '</li>';
                }).join('');
            }
        }

        function renderRuneforgeVoiceStatus(data) {
            const root = document.getElementById('runeforge_voice_status');
            if (!root) return;

            const pending = (data && data.pending_approval && typeof data.pending_approval === 'object') ? data.pending_approval : null;
            const report = (data && data.last_report && typeof data.last_report === 'object') ? data.last_report : null;

            let html = '<strong>Runeforge Voice Safety</strong>';
            if (pending && pending.type) {
                const pType = htmlEscape(String(pending.type));
                const created = htmlEscape(String(pending.created_at || 'unknown'));
                html += '<div class="snapshot-warning-item bad" style="margin-top:6px;">Pending approval: ' + pType + ' (' + created + ')</div>';
            } else {
                html += '<div class="snapshot-warning-item good" style="margin-top:6px;">No pending approvals.</div>';
            }

            if (report) {
                const actionType = htmlEscape(String(report.action_type || report.execution_method || 'n/a'));
                const okText = report.ok === false ? 'failed' : 'ok';
                const est = (report.estimated_restored_mb !== undefined && report.estimated_restored_mb !== null)
                    ? (' | est. restored: ' + htmlEscape(String(report.estimated_restored_mb)) + ' MB')
                    : '';
                html += '<div class="muted" style="margin-top:6px;">Last report: ' + actionType + ' (' + okText + ')' + est + '</div>';
            } else {
                html += '<div class="muted" style="margin-top:6px;">No execution report yet.</div>';
            }

            root.innerHTML = html;
        }

        function renderDelegationFlow(data) {
            const summary = document.getElementById('delegation_flow_summary');
            const chipsRoot = document.getElementById('delegation_flow_chips');
            const timelineRoot = document.getElementById('delegation_flow_timeline');
            const raw = document.getElementById('delegation_flow_raw');
            if (!summary || !chipsRoot || !timelineRoot || !raw) return;

            if (!data || data.ok === false) {
                summary.innerHTML = '<div class="agent-item"><strong>Delegation Flow</strong><div class="muted">Unavailable</div></div>';
                chipsRoot.innerHTML = '';
                timelineRoot.innerHTML = '';
                raw.textContent = JSON.stringify(data || { ok: false, message: 'unavailable' }, null, 2);
                return;
            }

            const c = data.counts || {};
            const q = data.queue || {};
            const accepted = data.accepted_by_agent || {};
            const verification = data.verification || {};
            const latestPacketId = String(data.latest_packet_id || '').trim();
            const timeline = Array.isArray(data.timeline) ? data.timeline : [];

            const cards = [
                { title: 'Submitted', value: Number(c.submitted_items || 0), sub: Number(c.submitted_packets || 0) + ' packet(s)' },
                { title: 'Reviewed', value: Number(c.reviewed_items || 0), sub: Number(c.reviewed_packets || 0) + ' packet(s)' },
                { title: 'Dispatched', value: Number(c.dispatched_items || 0), sub: Number(c.accepted_items || 0) + ' accepted' },
                { title: 'In Progress', value: Number(q.in_progress || 0), sub: Number(q.queued || 0) + ' queued' },
                { title: 'Completed', value: Number(c.completed_items || 0), sub: 'from bus events' },
            ];

            const acceptedText = Object.keys(accepted).length
                ? Object.entries(accepted).map(([k, v]) => htmlEscape(String(k)) + ': ' + htmlEscape(String(v))).join(' | ')
                : 'No agent acceptance events yet';

            const latestText = latestPacketId || 'none';

            summary.innerHTML = cards.map((item) => (
                '<div class="agent-item"><strong>' + htmlEscape(item.title) + '</strong>'
                + '<div style="font-size:22px;margin-top:4px;">' + htmlEscape(String(item.value)) + '</div>'
                + '<div class="muted">' + htmlEscape(item.sub) + '</div></div>'
            )).join('')
                + '<div class="agent-item"><strong>Latest Packet</strong><div class="muted" style="margin-top:6px;">' + htmlEscape(latestText) + '</div></div>'
                + '<div class="agent-item" style="grid-column: 1 / -1;"><strong>Accepted By Agent</strong><div class="muted">' + acceptedText + '</div></div>';

            const chips = [
                {
                    label: 'Verified',
                    value: Number(verification.verified || 0),
                    style: 'border-color:#4CC46A;color:#4CC46A;background:rgba(76,196,106,0.12);',
                },
                {
                    label: 'Blocked',
                    value: Number(verification.blocked || 0),
                    style: 'border-color:#FF4D4D;color:#FF4D4D;background:rgba(255,77,77,0.12);',
                },
                {
                    label: 'Rerouted',
                    value: Number(verification.rerouted || 0),
                    style: 'border-color:#FFB84D;color:#FFB84D;background:rgba(255,184,77,0.12);',
                },
            ];

            chipsRoot.innerHTML = chips
                .map((chip) => '<span class="pill" style="margin-right:8px;padding:4px 10px;' + chip.style + '">'
                    + htmlEscape(chip.label) + ': ' + htmlEscape(String(chip.value)) + '</span>')
                .join('');

            if (!timeline.length) {
                timelineRoot.innerHTML = '<div class="agent-item" style="grid-column: 1 / -1;"><strong>Recent Review Timeline</strong><div class="muted">No review packets yet.</div></div>';
            } else {
                timelineRoot.innerHTML = '<div class="agent-item" style="grid-column: 1 / -1;"><strong>Recent Review Timeline</strong><div class="muted">Most recent packet waves and target dispatch mix.</div>'
                    + '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">'
                    + timeline.map((entry) => {
                        const packetId = htmlEscape(String(entry.packet_id || 'packet'));
                        const dispatched = htmlEscape(String(entry.dispatched || 0));
                        const stamp = htmlEscape(String(entry.timestamp || ''));
                        const byTarget = (entry.by_target && typeof entry.by_target === 'object')
                            ? Object.entries(entry.by_target).map(([k, v]) => htmlEscape(String(k)) + ':' + htmlEscape(String(v))).join(' | ')
                            : '';
                        return '<span class="pill" style="padding:6px 8px;line-height:1.3;">'
                            + '<strong>' + packetId + '</strong><br/>'
                            + 'dispatch: ' + dispatched + '<br/>'
                            + (byTarget ? (byTarget + '<br/>') : '')
                            + '<span class="muted" style="font-size:11px;">' + stamp + '</span>'
                            + '</span>';
                    }).join('')
                    + '</div></div>';
            }

            raw.textContent = JSON.stringify(data, null, 2);
        }

        async function refreshDelegationFlowPanel() {
            const data = await fetchJsonWithTimeout('/api/delegation/flow', 6000);
            renderDelegationFlow(data);
        }

        async function refreshOsStatePanel() {
            const stateEl = document.getElementById('os_state');
            const diffEl = document.getElementById('os_state_diff');
            if (!stateEl || !diffEl) return;

            const stateData = await fetchJsonWithTimeout('/api/os/state?events=25', 6000);
            if (!stateData || stateData.ok === false) {
                stateEl.textContent = JSON.stringify(stateData || { ok: false, message: 'state unavailable' }, null, 2);
                return;
            }

            stateEl.textContent = JSON.stringify(stateData, null, 2);

            if (!previousOsState) {
                previousOsState = stateData;
                diffEl.textContent = JSON.stringify({ ok: true, message: 'baseline captured' }, null, 2);
                return;
            }

            const diffRes = await fetch('/api/os/state/diff', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ previous: previousOsState, current: stateData }),
            });
            const diffData = await diffRes.json();
            diffEl.textContent = JSON.stringify(diffData, null, 2);
            previousOsState = stateData;
        }

        async function refreshBusInspector() {
            const root = document.getElementById('bus_inspector');
            if (!root) return;
            const limitInput = document.getElementById('bus_limit');
            const kindInput = document.getElementById('bus_kind');
            const queryInput = document.getElementById('bus_query');
            const rawLimit = limitInput ? Number(limitInput.value || 80) : 80;
            const limit = Math.max(10, Math.min(300, Number.isFinite(rawLimit) ? rawLimit : 80));
            const kind = kindInput ? String(kindInput.value || 'events,commands,state') : 'events,commands,state';
            const query = queryInput ? encodeURIComponent(String(queryInput.value || '').trim()) : '';
            const data = await fetchJsonWithTimeout('/api/bus/inspect?limit=' + String(limit) + '&kind=' + encodeURIComponent(kind) + '&q=' + query, 6000);
            root.textContent = JSON.stringify(data, null, 2);
        }

        async function refresh() {
            document.getElementById('toast').textContent = 'Refreshing...';

            const statusData = await fetchJsonWithTimeout('/api/status');
            const eventsData = await fetchJsonWithTimeout('/api/events?limit=40');
            const snapData = await fetchJsonWithTimeout('/api/snapshot');
            const sealData = await fetchJsonWithTimeout('/api/archivist/seal');
            const voiceData = await fetchJsonWithTimeout('/api/runeforge/voice_status');
            const delegationData = await fetchJsonWithTimeout('/api/delegation/flow');

            if (statusData && statusData.agent_state) {
                renderAgents(statusData.agent_state);
                refreshTargetDropdown(statusData.agent_state);
                renderAgentTaskTracker(statusData.agent_tasks || { items: [] });
            } else {
                document.getElementById('agents').innerHTML = '<div class="muted">Status unavailable.</div>';
                renderAgentTaskTracker({ items: [] });
            }

            document.getElementById('events').textContent = JSON.stringify((eventsData && eventsData.items) ? eventsData.items : eventsData, null, 2);
            document.getElementById('snapshot').textContent = JSON.stringify(snapData, null, 2);
            renderSnapshotDashboard(snapData);
            renderRuneforgeVoiceStatus(voiceData);
            renderDelegationFlow(delegationData);
            document.getElementById('seal').textContent = JSON.stringify(sealData, null, 2);

            if (currentView === 'view_os_state') {
                await refreshOsStatePanel();
            }
            if (currentView === 'view_bus') {
                await refreshBusInspector();
            }
            if (currentView === 'view_delegation') {
                await refreshDelegationFlowPanel();
            }
            if (currentView === 'view_bossgate_map') {
                await refreshBossGateMap(false);
            }

            const failed = [statusData, eventsData, snapData, sealData, voiceData, delegationData].filter(x => x && x.ok === false).length;
            document.getElementById('toast').textContent = failed ? ('Loaded with ' + failed + ' endpoint issue(s).') : 'Loaded successfully.';
        }

        // === SoundForge Bundle UI Logic ===
        async function exportSoundforgeBundle() {
            const btn = event && event.target;
            if (btn) btn.disabled = true;
            try {
                const res = await fetch('/api/soundforge/export_bundle', { method: 'POST' });
                if (!res.ok) throw new Error('Export failed');
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'exported.B4Gsoundforge';
                document.body.appendChild(a);
                a.click();
                setTimeout(() => { document.body.removeChild(a); window.URL.revokeObjectURL(url); }, 100);
                setSoundSchemeStatus('Exported bundle downloaded.');
            } catch (e) {
                setSoundSchemeStatus('Export failed: ' + e);
            } finally {
                if (btn) btn.disabled = false;
            }
        }

        function showImportBundleDialog() {
            document.getElementById('soundforge_bundle_file').click();
        }

        async function handleImportBundle(event) {
            const file = event.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('bundle', file);
            formData.append('scheme_name', file.name.replace(/\\.(B4Gsoundforge|B4Gsoundstage)$/i, ''));
            setSoundSchemeStatus('Importing bundle...');
            try {
                const res = await fetch('/api/soundforge/import_bundle', { method: 'POST', body: formData });
                const data = await res.json();
                if (!data.ok) throw new Error(data.message || 'Import failed');
                setSoundSchemeStatus('Imported: ' + data.message);
                await listSoundforgeSchemes();
            } catch (e) {
                setSoundSchemeStatus('Import failed: ' + e);
            }
        }

        async function listSoundforgeSchemes() {
            try {
            const res = await fetch('/api/soundforge/list_schemes');
                const data = await res.json();
                if (!data.ok) throw new Error('Failed to list schemes');
            const el = document.getElementById('soundforge_schemes_list');
                if (el) {
                    el.innerHTML = 'Available Schemes: ' + (data.schemes && data.schemes.length ? data.schemes.map(s => `<span class="pill">${s}</span>`).join(' ') : 'None');
                }
            } catch (e) {
                setSoundSchemeStatus('Failed to list schemes: ' + e);
            }
        }

        function setSoundSchemeStatus(msg) {
            const el = document.getElementById('sound_scheme_status');
            if (el) el.textContent = msg;
        }

        async function saveSoundScheme() {
            const payload = {
                config: (soundScheme && typeof soundScheme.active_config === 'object') ? soundScheme.active_config : soundScheme,
            };
            const res = await fetch('/api/soundforge/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data && data.ok) {
                setSoundSchemeStatus('SoundForge config saved.');
            } else {
                setSoundSchemeStatus('Failed to save SoundForge config.');
            }
        }

        function loadSoundScheme() {
            document.getElementById('sound_scheme_file').click();
        }

        function createNewScheme() {
            soundScheme = {
                available_schemes: (soundScheme && Array.isArray(soundScheme.available_schemes)) ? soundScheme.available_schemes : [],
                active_config: { name: 'new-scheme', created_at: new Date().toISOString(), global: {}, per_app: {} },
            };
            renderSoundEvents();
            setSoundSchemeStatus('Created in-memory scheme draft.');
        }

        async function handleSchemeFile(event) {
            const file = event.target.files[0];
            if (!file) return;
            try {
                const text = await file.text();
                soundScheme = {
                    available_schemes: (soundScheme && Array.isArray(soundScheme.available_schemes)) ? soundScheme.available_schemes : [],
                    active_config: JSON.parse(text),
                };
                renderSoundEvents();
                setSoundSchemeStatus('Loaded scheme from file: ' + file.name);
            } catch (e) {
                setSoundSchemeStatus('Failed to load scheme file: ' + e);
            }
        }

        // Call on load
        wireInlineClickFallback();
        iconForgeLoadSectionCollapseState();
        switchView(currentView);
        refreshPinState();
        refreshChatEndpoints();
        refreshAgentMaker();
        refreshSecurityState();
        refreshSecretsList();
        refreshOnboardingStatus();
        refreshSchedulerStatus();
        refreshCicdStatus();
        applyAssetIcons();
        initIconForgeStudio();
        applyUrlLaunchContext();
        toggleWizardIconSource();
        toggleMakerIconSource();
        setWizardStep(1);
        syncWizardStateMachinePreview();
        applySelectedStateMachineTemplate();
        refresh();
        refreshBossGateAccess();
        listSoundforgeSchemes();
        setInterval(refresh, 4000);
        setInterval(refreshPinState, 3000);
    </script>
</body>
</html>
"""


def _read_ass_session_handoff() -> dict:
    encoded = str(os.environ.get("ASS_SESSION_HANDOFF_B64", "") or "").strip()
    if not encoded:
        return {}
    try:
        raw = base64.b64decode(encoded)
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _validate_ass_session_handoff(handoff: dict, *, expected_ticket: str, expected_target: str) -> str:
    if not handoff:
        return "No A.S.S. launch handoff is available."

    user_id = str(handoff.get("userId", "") or "").strip()
    username = str(handoff.get("username", "") or "").strip()
    if not user_id or not username:
        return "A.S.S. launch handoff is missing required identity."

    issued_at_raw = handoff.get("ts")
    try:
        issued_at = int(issued_at_raw)
    except (TypeError, ValueError):
        return "A.S.S. launch handoff is missing a valid issued timestamp."

    now = int(time.time())
    if issued_at <= 0 or issued_at > now + 30:
        return "A.S.S. launch handoff has an invalid issued timestamp."
    if now - issued_at > _ASS_HANDOFF_MAX_AGE_SECONDS:
        return "A.S.S. launch handoff has expired."

    actual_ticket = str(handoff.get("launchTicketId", "") or "").strip()
    actual_target = str(handoff.get("targetApp", "") or "").strip().lower()
    if actual_ticket != expected_ticket or actual_target != expected_target:
        return "Launch ticket mismatch."

    if expected_ticket in _ASS_CONSUMED_LAUNCH_TICKETS:
        return "Launch ticket has already been used."

    return ""


def _build_launch_ticket_bootstrap_script() -> str:
    launch_ticket = str(request.args.get("launch_ticket", "") or "").strip()
    target_app = str(request.args.get("target_app", "") or "").strip()
    launcher = str(request.args.get("launcher", "") or "").strip()
    if not launch_ticket or not target_app or launcher.lower() != "ass":
        return ""

    payload = json.dumps(
        {
            "ticketId": launch_ticket,
            "targetApp": target_app,
        }
    )
    return f"""
<script>
(() => {{
  const launchTicketPayload = {payload};
  window.__bossforgeLaunchTicket = launchTicketPayload;
  window.__bossforgeLaunchSession = {{ ok: false, pending: true }};
  fetch('/api/auth/launch-ticket/exchange', {{
    method: 'POST',
    headers: {{ 'Content-Type': 'application/json' }},
    body: JSON.stringify(launchTicketPayload),
  }})
    .then((response) => response.json())
    .then((data) => {{
      window.__bossforgeLaunchSession = data;
      try {{
        sessionStorage.setItem('bossforge_launch_session', JSON.stringify(data));
      }} catch (_err) {{}}
    }})
    .catch((error) => {{
      window.__bossforgeLaunchSession = {{
        ok: false,
        message: error && error.message ? error.message : 'Launch ticket exchange failed.',
      }};
    }});
}})();
</script>
"""


@app.get("/")
def index():
    bootstrap = _build_launch_ticket_bootstrap_script()
    if bootstrap:
        return render_template_string(PAGE.replace("</body>", bootstrap + "\n</body>"))
    return render_template_string(PAGE)


@app.post("/api/auth/launch-ticket/exchange")
def auth_launch_ticket_exchange():
    payload = request.get_json(force=True, silent=True) or {}
    ticket_id = str(payload.get("ticketId", "") or payload.get("launchTicketId", "")).strip()
    target_app = str(payload.get("targetApp", "")).strip().lower()
    handoff = _read_ass_session_handoff()

    if not ticket_id or not target_app:
        return jsonify({"ok": False, "message": "ticketId and targetApp are required."}), 400
    validation_error = _validate_ass_session_handoff(
        handoff,
        expected_ticket=ticket_id,
        expected_target=target_app,
    )
    if validation_error:
        status = 403 if validation_error == "Launch ticket mismatch." else 409 if "already been used" in validation_error else 401
        return jsonify({"ok": False, "message": validation_error}), status

    session = {
        "userId": str(handoff.get("userId", "")).strip(),
        "username": str(handoff.get("username", "")).strip(),
        "roles": handoff.get("roles") if isinstance(handoff.get("roles"), list) else [],
        "targetApp": target_app,
        "launchTicketId": ticket_id,
        "issuedAt": handoff.get("ts"),
        "bosskey": handoff.get("bosskey") if isinstance(handoff.get("bosskey"), dict) else {},
        "source": "ass",
    }
    _ASS_CONSUMED_LAUNCH_TICKETS.add(ticket_id)
    return jsonify({"ok": True, "session": session})


@app.get("/api/assets/icons/<path:filename>")
def serve_icon_asset(filename: str):
    safe_name = str(filename or "").replace("\\", "/").strip("/")
    if not safe_name:
        return jsonify({"ok": False, "message": "filename is required"}), 400

    icon_root = (PROJECT_ROOT / "assets" / "icons").resolve()
    candidate = (icon_root / safe_name).resolve()
    try:
        candidate.relative_to(icon_root)
    except Exception:
        return jsonify({"ok": False, "message": "invalid icon path"}), 400

    allowed = {".png", ".svg", ".ico", ".gif"}
    if candidate.suffix.lower() not in allowed:
        return jsonify({"ok": False, "message": "unsupported icon extension"}), 400
    if not candidate.exists() or not candidate.is_file():
        return jsonify({"ok": False, "message": "icon not found"}), 404
    return send_file(candidate)


@app.get("/api/status")
def status():
    latest = bus.read_latest_events(limit=30)
    return jsonify(
        {
            "name": "BossForgeOS Control Hall",
            "status": "online",
            "agents": AGENT_STATUS,
            "agent_state": read_agent_state(),
            "agent_tasks": load_agent_task_state(),
            "recent_events": latest,
        }
    )


@app.get("/api/os/state")
def os_state_snapshot():
    event_limit = int(request.args.get("events", "30"))
    payload = build_os_state(root=bus.root, event_limit=event_limit)
    return jsonify(payload)


@app.post("/api/os/state/diff")
def os_state_diff():
    payload = request.get_json(force=True, silent=True) or {}
    previous = payload.get("previous") if isinstance(payload.get("previous"), dict) else {}
    current = payload.get("current") if isinstance(payload.get("current"), dict) else {}
    if not current:
        current = build_os_state(root=bus.root, event_limit=30)
    result = diff_os_states(previous=previous, current=current)
    return jsonify(result)


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.post("/api/command")
def command():
    payload = request.get_json(force=True, silent=True) or {}
    target = payload.get("target")
    command_name = payload.get("command")
    args = payload.get("args") or {}

    if not target or not command_name:
        return jsonify({"ok": False, "message": "target and command are required"}), 400

    path = bus.emit_command(target=target, command=command_name, args=args, issued_by="control_hall")
    return jsonify({"ok": True, "written": str(path)})

# === Anvil Secured Shuttle Launcher Endpoint ===
@app.post("/api/launch_anvil_shuttle")
def launch_anvil_shuttle():
    try:
        script = os.path.join(PROJECT_ROOT, "launch_anvil_shuttle.py")
        if not os.path.exists(script):
            return jsonify({"ok": False, "message": "Launcher script missing."}), 500
        # Launch as detached process
        subprocess.Popen([sys.executable, script], cwd=PROJECT_ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "message": str(e)}), 500


@app.get("/api/events")
def events():
    limit = int(request.args.get("limit", "50"))
    return jsonify({"items": bus.read_latest_events(limit=limit)})


@app.get("/api/bus/inspect")
def bus_inspect():
    limit = max(10, min(300, int(request.args.get("limit", "80"))))
    kind_raw = str(request.args.get("kind", "events,commands,state")).strip().lower()
    query = str(request.args.get("q", "")).strip().lower()
    selected_kinds = {k.strip() for k in kind_raw.split(",") if k.strip()}
    if not selected_kinds:
        selected_kinds = {"events", "commands", "state"}

    def _matches(payload: dict[str, object], file_name: str) -> bool:
        if not query:
            return True
        haystack = [file_name]
        for key in ("source", "target", "event", "command", "service"):
            value = payload.get(key)
            if isinstance(value, str):
                haystack.append(value)
        return query in " ".join(haystack).lower()

    def _read_latest(folder: Path, cap: int) -> list[dict[str, object]]:
        out: list[dict[str, object]] = []
        for file_path in sorted(folder.glob("*.json"), reverse=True)[:cap]:
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {"ok": False, "error": "invalid-json"}
            if not isinstance(payload, dict):
                payload = {"value": payload}
            if not _matches(payload, file_path.name):
                continue
            payload["_file"] = file_path.name
            out.append(payload)
        return out

    events_payload: list[dict[str, object]] = []
    if "events" in selected_kinds:
        for item in bus.read_latest_events(limit=limit * 6):
            payload = item if isinstance(item, dict) else {"value": item}
            if not _matches(payload, "event"):
                continue
            events_payload.append(payload)
            if len(events_payload) >= limit:
                break

    commands_payload = _read_latest(bus.commands, limit) if "commands" in selected_kinds else []
    state_payload = _read_latest(bus.state, limit) if "state" in selected_kinds else []

    return jsonify(
        {
            "ok": True,
            "root": str(bus.root),
            "filters": {
                "kind": sorted(selected_kinds),
                "query": query,
                "limit": limit,
            },
            "counts": {
                "events": bus.count_json_files(bus.events),
                "commands": bus.count_json_files(bus.commands),
                "state": bus.count_json_files(bus.state),
            },
            "latest": {
                "events": events_payload,
                "commands": commands_payload,
                "state": state_payload,
            },
        }
    )


@app.get("/api/snapshot")
def snapshot():
    return jsonify(snapshot_all())


@app.get("/api/runeforge/voice_status")
def runeforge_voice_status():
    return jsonify(runeforge_voice_service.get_voice_status(bus))


@app.get("/api/delegation/flow")
def delegation_flow_status():
    events = bus.read_latest_events(limit=300)
    worker_agents = {"runeforge", "codemage", "devlot", "test_sentinel"}

    submitted_packets = 0
    submitted_items = 0
    reviewed_packets = 0
    reviewed_items = 0
    dispatched_items = 0
    accepted_items = 0
    completed_items = 0
    rerouted_items = 0
    verified_items = 0
    accepted_by_agent: dict[str, int] = {}
    timeline_entries: list[dict[str, object]] = []
    latest_packet_id = ""

    latest_submission_at = ""
    latest_review_at = ""

    for item in events:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source", "")).strip().lower()
        event_name = str(item.get("event", "")).strip()
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        stamp = str(item.get("timestamp", "")).strip()

        if source == "archivist" and event_name == "delegation_submitted_to_runeforge":
            submitted_packets += 1
            submitted_items += int(data.get("submitted", 0) or 0)
            if stamp:
                latest_submission_at = stamp

        if source == "runeforge" and event_name == "delegation_review_completed":
            packet_id = str(data.get("packet_id", "")).strip()
            reviewed_packets += 1
            reviewed_items += int(data.get("submitted", 0) or 0)
            dispatched_items += int(data.get("dispatched", 0) or 0)
            if packet_id:
                latest_packet_id = packet_id

            by_target: dict[str, int] = {}
            for dispatch_item in data.get("items", []) if isinstance(data.get("items"), list) else []:
                if not isinstance(dispatch_item, dict):
                    continue
                target = str(dispatch_item.get("target", "")).strip().lower()
                if not target:
                    continue
                by_target[target] = by_target.get(target, 0) + 1

            timeline_entries.append(
                {
                    "packet_id": packet_id or "unknown",
                    "timestamp": stamp,
                    "submitted": int(data.get("submitted", 0) or 0),
                    "dispatched": int(data.get("dispatched", 0) or 0),
                    "by_target": by_target,
                }
            )
            if stamp:
                latest_review_at = stamp

        if source in worker_agents and event_name == "command:work_item":
            if bool(data.get("ok", False)):
                accepted_items += 1
                accepted_by_agent[source] = accepted_by_agent.get(source, 0) + 1

        if source in worker_agents and event_name == "work_item_completed":
            completed_items += int(data.get("completed_count", 0) or 0)
            if bool(data.get("post_fix_verified", False)):
                verified_items += int(data.get("completed_count", 0) or 0)

        if source in worker_agents and event_name == "post_fix_regression_detected":
            rerouted_items += 1

    def _read_items(path: Path) -> list[dict[str, object]]:
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        raw = payload.get("items", []) if isinstance(payload, dict) else []
        return [x for x in raw if isinstance(x, dict)] if isinstance(raw, list) else []

    queue_files = {
        "runeforge": bus.state / "runeforge_tasks.json",
        "codemage": bus.state / "codemage_work_packets.json",
        "devlot": bus.state / "devlot_tasks.json",
        "test_sentinel": bus.state / "test_sentinel_tasks.json",
    }

    queued = 0
    in_progress = 0
    blocked = 0
    delegated_seen = 0

    for _, path in queue_files.items():
        for task in _read_items(path):
            is_delegated = bool(task.get("delegated_handoff", False)) or str(task.get("source", "")).strip().lower() == "archivist_review"
            if not is_delegated:
                continue
            delegated_seen += 1
            status = str(task.get("status", "queued")).strip().lower()
            if status == "in_progress":
                in_progress += 1
            elif status == "queued":
                queued += 1
            elif status == "blocked":
                blocked += 1

    timeline = list(reversed(timeline_entries[:8]))
    if not latest_packet_id and timeline:
        latest_packet_id = str(timeline[-1].get("packet_id", "")).strip()

    return jsonify(
        {
            "ok": True,
            "counts": {
                "submitted_packets": submitted_packets,
                "submitted_items": submitted_items,
                "reviewed_packets": reviewed_packets,
                "reviewed_items": reviewed_items,
                "dispatched_items": dispatched_items,
                "accepted_items": accepted_items,
                "completed_items": completed_items,
            },
            "queue": {
                "delegated_items_seen": delegated_seen,
                "in_progress": in_progress,
                "queued": queued,
                "blocked": blocked,
            },
            "verification": {
                "verified": verified_items,
                "blocked": blocked,
                "rerouted": rerouted_items,
            },
            "accepted_by_agent": accepted_by_agent,
            "latest_packet_id": latest_packet_id,
            "timeline": timeline,
            "latest": {
                "submission_at": latest_submission_at,
                "review_at": latest_review_at,
            },
        }
    )


@app.get("/api/archivist/seal")
def archivist_seal():
    path = bus.state / "archivist_seal_queue.json"
    if not path.exists():
        return jsonify({"pending": [], "history": []})
    try:
        return jsonify(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError):
        return jsonify({"pending": [], "history": [], "error": "invalid queue state"})


@app.get("/api/model/endpoints")
def model_endpoints():
    return jsonify(model_gateway_api.list_endpoints_from_state(str(bus.state / "model_endpoints.json")))


@app.get("/api/model/agents")
def model_agents():
    return jsonify(agentforge_api.list_agent_profiles())


@app.post("/api/model/agents/create")
def model_agents_create():
    payload = request.get_json(force=True, silent=True) or {}
    result = agentforge_api.create_agent_profile(payload)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/agentforge/agents/<name>/view")
def agentforge_agent_view(name: str):
    result = agentforge_api.view_agent_profile(
        name,
        viewer_id=str(request.args.get("viewer_id", "")).strip(),
        viewer_channel=str(request.args.get("viewer_channel", "")).strip(),
    )
    status = 200 if result.get("ok") else 404
    return jsonify(result), status


@app.post("/api/agentforge/agents/<name>/disclosure")
def agentforge_agent_disclosure(name: str):
    payload = request.get_json(force=True, silent=True) or {}
    result = agentforge_api.set_agent_disclosure_posture(name, str(payload.get("disclosure_posture", "")).strip())
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/bossgate/access/capabilities")
def bossgate_access_capabilities():
    user_id = str(request.args.get("user_id", "")).strip()
    return jsonify(_bossgate_authorization().capabilities_for_user(user_id))


@app.get("/api/bossgate/access/policy")
def bossgate_access_policy():
    return jsonify(model_gateway_api.bossgate_presence_policy())


@app.post("/api/bossgate/access/policy")
def bossgate_access_policy_update():
    payload = request.get_json(force=True, silent=True) or {}
    result = model_gateway_api.set_bossgate_presence_policy(
        accept_unknown_messages=bool(payload.get("accept_unknown_messages", False))
    )
    return jsonify(result), (200 if result.get("ok") else 400)


@app.post("/api/bossgate/access/roles")
def bossgate_access_roles():
    payload = request.get_json(force=True, silent=True) or {}
    permissions = payload.get("permissions") if isinstance(payload.get("permissions"), list) else []
    result = _bossgate_authorization().create_or_update_custom_role(
        acting_user=str(payload.get("acting_user", "")).strip(),
        role_name=str(payload.get("role_name", "")).strip(),
        permissions=[str(item) for item in permissions],
    )
    return jsonify(result), (200 if result.get("ok") else 403)


@app.post("/api/bossgate/access/users/<user_id>/roles")
def bossgate_access_user_roles(user_id: str):
    payload = request.get_json(force=True, silent=True) or {}
    roles = payload.get("roles") if isinstance(payload.get("roles"), list) else []
    result = _bossgate_authorization().assign_user_roles(
        acting_user=str(payload.get("acting_user", "")).strip(),
        user_id=str(user_id).strip(),
        roles=[str(item) for item in roles],
    )
    return jsonify(result), (200 if result.get("ok") else 403)


@app.post("/api/agentforge/icon/upload")
def agentforge_icon_upload():
    uploaded = request.files.get("icon")
    if uploaded is None:
        return jsonify({"ok": False, "message": "icon file is required"}), 400
    hint = str(request.form.get("icon_name", "agent_icon")).strip()
    result, status = agentforge_api.upload_icon(uploaded=uploaded, icon_name=hint, project_root=PROJECT_ROOT)
    return jsonify(result), status


@app.post("/api/agentforge/icon/create")
def agentforge_icon_create():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = agentforge_api.create_icon(payload=payload, project_root=PROJECT_ROOT)
    return jsonify(result), status


@app.post("/api/agentforge/icon/create_from_canvas")
def agentforge_icon_create_from_canvas():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = agentforge_api.create_icon_from_canvas(payload=payload, project_root=PROJECT_ROOT)
    return jsonify(result), status


@app.post("/api/agentforge/icon/create_animated_from_canvas")
def agentforge_icon_create_animated_from_canvas():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = agentforge_api.create_animated_icon_from_canvas(payload=payload, project_root=PROJECT_ROOT)
    return jsonify(result), status


@app.get("/api/iconforge/backups")
def iconforge_backups():
    result, status = iconforge_api.list_backups(PROJECT_ROOT)
    return jsonify(result), status


@app.get("/api/iconforge/preview")
def iconforge_preview():
    candidate, err, status = iconforge_api.resolve_preview_path(PROJECT_ROOT, request.args.get("path", ""))
    if err is not None:
        return jsonify(err), status
    return send_file(candidate)


@app.post("/api/iconforge/apply")
def iconforge_apply():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = iconforge_api.apply_icon(PROJECT_ROOT, payload)
    return jsonify(result), status


@app.post("/api/iconforge/refresh_cache")
def iconforge_refresh_cache():
    result, status = iconforge_api.refresh_icon_cache(PROJECT_ROOT)
    return jsonify(result), status


@app.post("/api/iconforge/restore")
def iconforge_restore():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = iconforge_api.restore_backup(PROJECT_ROOT, payload)
    return jsonify(result), status


@app.post("/api/iconforge/pack/export")
def iconforge_pack_export():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = iconforge_api.export_pack(PROJECT_ROOT, payload)
    return jsonify(result), status


@app.post("/api/iconforge/pack/import")
def iconforge_pack_import():
    payload = request.get_json(force=True, silent=True) or {}
    result, status = iconforge_api.import_pack(PROJECT_ROOT, payload)
    return jsonify(result), status


@app.post("/api/model/agents/triage")
def model_agents_triage():
    payload = request.get_json(force=True, silent=True) or {}
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else {}
    weights_raw = payload.get("weights")
    weights = weights_raw if isinstance(weights_raw, dict) else None
    return jsonify(model_gateway_api.triage_agent_candidates(incident=incident, weights=weights))


@app.post("/api/model/agents/delete")
def model_agents_delete():
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    result = model_gateway_api.delete_agent_profile(name)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/run")
def model_agents_run():
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    task = str(payload.get("task", "")).strip()
    endpoint = str(payload.get("endpoint", "")).strip()
    memory_context = payload.get("memory_context") if isinstance(payload.get("memory_context"), dict) else {}
    result = model_gateway_api.run_agent_profile(name, task, endpoint, memory_context=memory_context)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/agents/memory")
def model_agents_memory():
    name = str(request.args.get("name", "")).strip()
    limit = int(request.args.get("limit", "25"))
    result = model_gateway_api.recall_agent_memory(name=name, limit=limit)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/travel/discover")
def model_travel_discover():
    timeout = int(request.args.get("timeout", "5"))
    assistance_only = str(request.args.get("assistance_only", "false")).strip().lower() in {"1", "true", "yes", "on"}
    operator_id = str(request.args.get("operator_id", "")).strip()
    scope_id = str(request.args.get("scope_id", "")).strip()
    actor_type = str(request.args.get("actor_type", "human")).strip()
    result = model_gateway_api.discover_travel_targets(
        timeout=timeout,
        assistance_only=assistance_only,
        operator_id=operator_id,
        scope_id=scope_id,
        actor_type=actor_type,
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/travel/map")
def model_travel_map():
    refresh = str(request.args.get("refresh", "false")).strip().lower() in {"1", "true", "yes", "on"}
    timeout = int(request.args.get("timeout", "2"))
    result = model_gateway_api.bossgate_map_snapshot(refresh=refresh, timeout=timeout)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/travel/transfers")
def model_travel_transfers():
    limit = int(request.args.get("limit", "20"))
    result = _read_bossgate_transfers(limit=limit)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/travel/validate")
def model_travel_validate():
    payload = request.get_json(force=True, silent=True) or {}
    destination = str(payload.get("destination", "")).strip()
    result = model_gateway_api.validate_transfer_target(
        destination=destination,
        operator_id=str(payload.get("operator_id", "")).strip(),
        scope_id=str(payload.get("scope_id", "")).strip(),
        actor_type=str(payload.get("actor_type", "human")).strip(),
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/assistance")
def model_agents_assistance_set():
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    requested = bool(payload.get("requested", True))
    reason = str(payload.get("reason", "")).strip()
    result = model_gateway_api.set_agent_assistance_request(name=name, requested=requested, reason=reason)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/agents/assistance")
def model_agents_assistance_list():
    result = model_gateway_api.list_assistance_requests()
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/agents/locations")
def model_agents_locations():
    refresh = str(request.args.get("refresh", "false")).strip().lower() in {"1", "true", "yes", "on"}
    result = model_gateway_api.list_owned_agent_locations(refresh=refresh)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/chat")
def model_chat():
    payload = request.get_json(force=True, silent=True) or {}
    endpoint = str(payload.get("endpoint", "")).strip()
    prompt = str(payload.get("prompt", "")).strip()
    system = str(payload.get("system", "You are BossForgeOS assistant."))
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 900))

    if not endpoint or not prompt:
        return jsonify({"ok": False, "message": "endpoint and prompt are required"}), 400

    result = model_gateway_api.invoke_endpoint(endpoint, prompt, system, temperature, max_tokens)
    return jsonify(result)


@app.get("/api/security/state")
def security_state():
    return jsonify(security_api.read_security_state(bus.state / "security_sentinel.json"))


@app.post("/api/security/scan")
def security_scan():
    payload = request.get_json(force=True, silent=True) or {}
    path = str(payload.get("path", "")).strip()
    result, status = security_api.scan_workspace(path)
    return jsonify(result), status


@app.get("/api/security/secrets")
def security_secrets():
    return jsonify(security_api.list_secrets())


@app.post("/api/security/policy/set")
def security_policy_set():
    payload = request.get_json(force=True, silent=True) or {}
    agent_name = str(payload.get("agent", "")).strip()
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    result, status = security_api.set_policy(agent_name, [str(a) for a in actions])
    return jsonify(result), status


@app.post("/api/security/policy/check")
def security_policy_check():
    payload = request.get_json(force=True, silent=True) or {}
    agent_name = str(payload.get("agent", "")).strip()
    action = str(payload.get("action", "")).strip()
    return jsonify(security_api.check_policy(agent_name, action))


def _pin_overlay_is_running() -> bool:
    global PIN_OVERLAY_PROCESS
    if PIN_OVERLAY_PROCESS is None:
        return False
    return PIN_OVERLAY_PROCESS.poll() is None


def _terminate_pin_overlay() -> None:
    global PIN_OVERLAY_PROCESS, PIN_OVERLAY_VIEW
    if PIN_OVERLAY_PROCESS is None:
        PIN_OVERLAY_VIEW = ""
        return
    if PIN_OVERLAY_PROCESS.poll() is None:
        try:
            PIN_OVERLAY_PROCESS.terminate()
            PIN_OVERLAY_PROCESS.wait(timeout=3)
        except Exception:
            try:
                PIN_OVERLAY_PROCESS.kill()
            except Exception:
                pass
    PIN_OVERLAY_PROCESS = None
    PIN_OVERLAY_VIEW = ""


atexit.register(_terminate_pin_overlay)


@app.get("/api/pin/state")
def pin_state():
    global PIN_OVERLAY_PROCESS, PIN_OVERLAY_VIEW, PIN_OVERLAY_ALPHA
    out = ui_runtime_api.pin_state(PIN_OVERLAY_PROCESS, PIN_OVERLAY_VIEW, PIN_OVERLAY_ALPHA, _pin_overlay_is_running)
    PIN_OVERLAY_PROCESS = out.pop("_process", PIN_OVERLAY_PROCESS)
    PIN_OVERLAY_VIEW = out.pop("_view", PIN_OVERLAY_VIEW)
    return jsonify(out)


@app.post("/api/pin/launch")
def pin_launch():
    global PIN_OVERLAY_PROCESS, PIN_OVERLAY_VIEW, PIN_OVERLAY_ALPHA
    payload = request.get_json(force=True, silent=True) or {}
    view, alpha = ui_runtime_api.pin_launch_payload(payload, PIN_OVERLAY_ALPHA)

    overlay_path = ui_runtime_api.pin_overlay_path(__file__)
    if not overlay_path.exists():
        return jsonify({"ok": False, "message": f"overlay script missing: {overlay_path}"}), 500

    _terminate_pin_overlay()

    try:
        PIN_OVERLAY_PROCESS = subprocess.Popen(
            [sys.executable, str(overlay_path), "--view", view, "--base-url", "http://127.0.0.1:5005", "--alpha", str(alpha)]
        )
    except Exception as ex:
        PIN_OVERLAY_PROCESS = None
        PIN_OVERLAY_VIEW = ""
        return jsonify({"ok": False, "message": str(ex)}), 500

    PIN_OVERLAY_VIEW = view
    PIN_OVERLAY_ALPHA = alpha
    return jsonify({"ok": True, "running": True, "view": PIN_OVERLAY_VIEW, "alpha": PIN_OVERLAY_ALPHA})


@app.post("/api/pin/close")
def pin_close():
    global PIN_OVERLAY_ALPHA
    _terminate_pin_overlay()
    return jsonify({"ok": True, "running": False, "view": "", "alpha": PIN_OVERLAY_ALPHA})


def load_agent_task_state() -> dict:
    if not AGENT_TASK_TRACKER_PATH.exists():
        initial = task_tracker_api.default_agent_task_state(AGENT_ASSIGNMENTS_PATH)
        _save_json_state(AGENT_TASK_TRACKER_PATH, initial)
        return initial
    state = _load_json_state(
        AGENT_TASK_TRACKER_PATH,
        task_tracker_api.default_agent_task_state(AGENT_ASSIGNMENTS_PATH),
    )
    normalized = task_tracker_api.normalize_agent_task_state(state)
    if normalized != state:
        _save_json_state(AGENT_TASK_TRACKER_PATH, normalized)
    return normalized


def read_agent_state() -> dict[str, dict[str, str]]:
    return agent_state_api.read_agent_state(state_dir=bus.state, static_agents=AGENT_STATUS)


# === SoundForge Bundle Endpoints ===

SOUNDFORGE_CONFIG_PATH = str(soundforge_api.SOUNDFORGE_CONFIG_PATH)
LEGACY_SOUNDSTAGE_CONFIG_PATH = str(soundforge_api.LEGACY_SOUNDSTAGE_CONFIG_PATH)
SOUNDFORGE_SCHEMES_DIR = str(soundforge_api.SOUNDFORGE_SCHEMES_DIR)
LEGACY_SOUNDSTAGE_SCHEMES_DIR = str(soundforge_api.LEGACY_SOUNDSTAGE_SCHEMES_DIR)
SOUNDFORGE_SOUNDS_DIR = str(soundforge_api.SOUNDFORGE_SOUNDS_DIR)
soundforge_api.ensure_layout()

@app.get("/api/soundforge/config")
def soundforge_get_config():
    config = soundforge_api.load_active_config()
    return jsonify({"ok": True, "config": config})


@app.post("/api/soundforge/config")
def soundforge_save_config():
    payload = request.get_json(force=True, silent=True) or {}
    config = payload.get("config")
    if not isinstance(config, dict):
        return jsonify({"ok": False, "message": "config object is required"}), 400
    try:
        soundforge_api.save_active_config(config)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Failed to save config: {ex}"}), 500
    return jsonify({"ok": True, "message": "SoundForge config saved."})

@app.post("/api/soundforge/export_bundle")
@app.post("/api/soundstage/export_bundle")
def export_soundforge_bundle():
    """Export current config + all referenced sounds as a .B4Gsoundforge zip bundle."""
    try:
        bundle_path = soundforge_api.export_bundle(Path(SOUNDFORGE_SCHEMES_DIR) / "exported.B4Gsoundforge")
    except Exception as e:
        return jsonify({"ok": False, "message": f"Failed to export bundle: {e}"}), 500
    return send_file(str(bundle_path), as_attachment=True, download_name="exported.B4Gsoundforge")

@app.post("/api/soundforge/import_bundle")
@app.post("/api/soundstage/import_bundle")
def import_soundforge_bundle():
    """Import a .B4Gsoundforge zip bundle: extract config + sounds, rewrite config paths, activate scheme."""
    if "bundle" not in request.files:
        return jsonify({"ok": False, "message": "No bundle uploaded"}), 400
    bundle = request.files["bundle"]
    scheme_name = request.form.get("scheme_name", "imported_scheme")
    collision_policy = request.form.get("collision_policy", "rename")
    try:
        result = soundforge_api.import_bundle(
            bundle.stream,
            scheme_name=scheme_name,
            collision_policy=collision_policy,
        )
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Failed to import bundle: {ex}"}), 500
    return jsonify(
        {
            "ok": True,
            "message": f"Imported scheme '{result.get('scheme_name', scheme_name)}' and activated.",
            "result": result,
        }
    )

@app.get("/api/soundforge/list_schemes")
@app.get("/api/soundstage/list_schemes")
def list_soundforge_schemes():
    """List available imported SoundForge schemes."""
    schemes = soundforge_api.list_schemes()
    return jsonify({"ok": True, "schemes": schemes})


@app.post("/api/soundforge/activate_scheme")
@app.post("/api/soundstage/activate_scheme")
def activate_soundforge_scheme():
    payload = request.get_json(force=True, silent=True) or {}
    scheme_name = payload.get("scheme_name")
    if not isinstance(scheme_name, str) or not scheme_name.strip():
        return jsonify({"ok": False, "message": "scheme_name is required"}), 400
    try:
        result = soundforge_api.activate_scheme(scheme_name)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Failed to activate scheme: {ex}"}), 500
    return jsonify(result)


@app.post("/api/soundforge/validate_bundle")
@app.post("/api/soundstage/validate_bundle")
def validate_soundforge_bundle():
    if "bundle" not in request.files:
        return jsonify({"ok": False, "message": "No bundle uploaded"}), 400
    bundle = request.files["bundle"]
    try:
        report = soundforge_api.validate_bundle(bundle.stream)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Validation failed: {ex}"}), 500
    return jsonify(report)


@app.get("/api/soundforge/diagnostics")
@app.get("/api/soundstage/diagnostics")
def soundforge_diagnostics():
    try:
        report = soundforge_api.diagnose_config()
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Diagnostics failed: {ex}"}), 500
    return jsonify(report)


@app.get("/api/soundforge/migration_status")
@app.get("/api/soundstage/migration_status")
def soundforge_migration_status():
    try:
        status = soundforge_api.migration_status()
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Migration status failed: {ex}"}), 500
    return jsonify({"ok": True, "status": status})


@app.post("/api/soundforge/migrate_legacy")
@app.post("/api/soundstage/migrate_legacy")
def soundforge_migrate_legacy():
    payload = request.get_json(force=True, silent=True) or {}
    collision_policy = str(payload.get("collision_policy", "rename")).strip().lower()
    if collision_policy not in {"rename", "replace", "fail"}:
        return jsonify({"ok": False, "message": "collision_policy must be rename|replace|fail"}), 400
    try:
        result = soundforge_api.migrate_legacy_to_soundforge(collision_policy=collision_policy)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Migration failed: {ex}"}), 500
    return jsonify(result)


@app.post("/api/soundforge/finalize_soundstage_removal")
@app.post("/api/soundstage/finalize_removal")
def soundforge_finalize_soundstage_removal():
    payload = request.get_json(force=True, silent=True) or {}
    collision_policy = str(payload.get("collision_policy", "rename")).strip().lower()
    if collision_policy not in {"rename", "replace", "fail"}:
        return jsonify({"ok": False, "message": "collision_policy must be rename|replace|fail"}), 400
    try:
        result = soundforge_api.finalize_soundstage_removal(collision_policy=collision_policy)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Finalization failed: {ex}"}), 500
    code = 200 if result.get("ok") else 409
    return jsonify(result), code



###############################
# Collaborative Agent Editing #
###############################


def _collab_join_flow(
    agent_editors: dict[str, set[str]],
    agent_locks: dict[str, str],
    data: dict,
    *,
    emit_fn,
    join_room_fn,
) -> None:
    agent, presence = collab_api.join_agent(agent_editors, agent_locks, data)
    if not presence.get("ok"):
        emit_fn("presence", presence)
        return
    join_room_fn(agent)
    emit_fn("presence", presence, room=agent)


def _collab_leave_flow(
    agent_editors: dict[str, set[str]],
    agent_locks: dict[str, str],
    data: dict,
    *,
    emit_fn,
    leave_room_fn,
) -> None:
    agent, presence = collab_api.leave_agent(agent_editors, agent_locks, data)
    if not presence.get("ok"):
        emit_fn("presence", presence)
        return
    leave_room_fn(agent)
    emit_fn("presence", presence, room=agent)


def _collab_lock_flow(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict, *, emit_fn) -> None:
    agent, presence = collab_api.lock_agent(agent_editors, agent_locks, data)
    if not presence.get("ok"):
        emit_fn("presence", presence)
        return
    emit_fn("presence", presence, room=agent)


def _collab_unlock_flow(agent_editors: dict[str, set[str]], agent_locks: dict[str, str], data: dict, *, emit_fn) -> None:
    agent, presence = collab_api.unlock_agent(agent_editors, agent_locks, data)
    if not presence.get("ok"):
        emit_fn("presence", presence)
        return
    emit_fn("presence", presence, room=agent)


def _collab_edit_flow(data: dict, *, emit_fn) -> None:
    agent, payload = collab_api.edit_agent_payload(data)
    if not payload.get("ok"):
        emit_fn("agent_edit", payload)
        return
    emit_fn("agent_edit", payload, room=agent, include_self=False)


try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    socketio = SocketIO(app, cors_allowed_origins="*")
    # In-memory presence and edit state (not persistent)
    agent_editors = {}  # {agent_name: set(user_ids)}
    agent_locks = {}    # {agent_name: user_id}

    @socketio.on('join_agent')
    def handle_join_agent(data):
        _collab_join_flow(agent_editors, agent_locks, data, emit_fn=emit, join_room_fn=join_room)

    @socketio.on('leave_agent')
    def handle_leave_agent(data):
        _collab_leave_flow(agent_editors, agent_locks, data, emit_fn=emit, leave_room_fn=leave_room)

    @socketio.on('lock_agent')
    def handle_lock_agent(data):
        _collab_lock_flow(agent_editors, agent_locks, data, emit_fn=emit)

    @socketio.on('unlock_agent')
    def handle_unlock_agent(data):
        _collab_unlock_flow(agent_editors, agent_locks, data, emit_fn=emit)

    @socketio.on('edit_agent')
    def handle_edit_agent(data):
        _collab_edit_flow(data, emit_fn=emit)
except ImportError:
    socketio = None

SCHEDULER_STATE_PATH = bus.state / "control_hall_scheduler.json"
CICD_STATE_PATH = bus.state / "control_hall_cicd.json"
ONBOARDING_STATE_PATH = bus.state / "control_hall_onboarding.json"


def _load_json_state(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return dict(fallback)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    return payload if isinstance(payload, dict) else dict(fallback)


def _save_json_state(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _read_bossgate_transfers(limit: int = 20) -> dict:
    path = bus.state / "bossgate_transfers.jsonl"
    if not path.exists():
        return {"ok": True, "items": []}
    entries = []
    try:
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                entries.append(item)
    except OSError as ex:
        return {"ok": False, "message": str(ex), "items": []}
    lim = max(1, int(limit))
    normalized = []
    for item in entries[-lim:]:
        normalized.append(
            {
                **item,
                "presence_color": str(item.get("presence_color", "")).strip() or "grey",
                "agent_name": str(item.get("agent_name", "")).strip(),
                "discovery_state": str(item.get("discovery_state", "")).strip() or "revealed",
            }
        )
    return {"ok": True, "items": normalized}


def _default_scheduler_state() -> dict:
    return ops_runtime_api.default_scheduler_state()


def _default_cicd_state() -> dict:
    return ops_runtime_api.default_cicd_state()


def _default_onboarding_state() -> dict:
    return onboarding_api.default_state()


@app.route('/api/scheduler', methods=['GET', 'POST'])
def scheduler():
    state = _load_json_state(SCHEDULER_STATE_PATH, _default_scheduler_state())

    if request.method == 'GET':
        return jsonify(ops_runtime_api.scheduler_get(state))

    payload = request.get_json(force=True, silent=True) or {}
    result, status = ops_runtime_api.scheduler_post(state=state, payload=payload, project_root=PROJECT_ROOT)
    if status == 200 and result.get("ok"):
        _save_json_state(SCHEDULER_STATE_PATH, {k: v for k, v in result.items() if k not in {"ok", "message", "result"}})
    return jsonify(result), status


@app.route('/api/cicd', methods=['GET', 'POST'])
def cicd():
    state = _load_json_state(CICD_STATE_PATH, _default_cicd_state())

    if request.method == 'GET':
        return jsonify(ops_runtime_api.cicd_get(state))

    payload = request.get_json(force=True, silent=True) or {}
    result, status = ops_runtime_api.cicd_post(state=state, payload=payload, project_root=PROJECT_ROOT)
    if status == 200 and result.get("ok"):
        _save_json_state(CICD_STATE_PATH, {k: v for k, v in result.items() if k != "ok"})
    return jsonify(result), status


@app.route('/api/onboarding', methods=['POST'])
@app.route('/onboarding', methods=['POST'])
def onboarding():
    state = _load_json_state(ONBOARDING_STATE_PATH, _default_onboarding_state())
    payload = request.get_json(force=True, silent=True) or {}
    step = str(payload.get("step", "")).strip().lower()
    result, status = onboarding_api.apply_step(state, step, PROJECT_ROOT, bus.root)
    if status == 200:
        _save_json_state(ONBOARDING_STATE_PATH, {k: v for k, v in result.items() if k != "ok"})
    return jsonify(result), status


@app.route('/api/onboarding/status', methods=['GET'])
@app.route('/onboarding', methods=['GET'])
def onboarding_status():
    state = _load_json_state(ONBOARDING_STATE_PATH, _default_onboarding_state())
    return jsonify(onboarding_api.status_payload(state))


def main() -> None:
    if socketio is not None:
        socketio.run(app, host="127.0.0.1", port=5005, debug=False)
    else:
        from werkzeug.serving import run_simple
        run_simple("127.0.0.1", 5005, app, use_reloader=False, use_debugger=False, threaded=True)


if __name__ == "__main__":
    main()
