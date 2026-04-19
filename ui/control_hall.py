import atexit
import base64
import json
import math
import os
import subprocess
import sys

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
from werkzeug.utils import secure_filename


from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.security.security_sentinel_agent import SecuritySentinelAgent
from core.state.os_state import build_os_state, diff_os_states
from modules.os_snapshot import snapshot_all


app = Flask(__name__)
bus = RuneBus(resolve_root_from_env())
socketio = None
PIN_OVERLAY_PROCESS = None
PIN_OVERLAY_VIEW = ""
PIN_OVERLAY_ALPHA = 0.95
AGENTFORGE_POOL_PATH = PROJECT_ROOT / "state" / "agentforge_custom_pool.json"

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
        .shell { display:grid; grid-template-columns: 250px 1fr; min-height:100vh; }
        @media (max-width: 980px) { .shell { grid-template-columns: 1fr; } }
        .side {
            border-right:1px solid var(--line);
            background:linear-gradient(180deg,#101015,#0D0D11 70%, #0A0A0C);
            padding:14px;
            box-shadow: inset -1px 0 0 rgba(255,122,47,0.10);
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
        .wrap { max-width:1200px; margin:0 auto; padding:18px; display:grid; gap:14px; }
        .card {
            background:linear-gradient(180deg,var(--panel2),var(--panel));
            border:1px solid var(--line);
            border-radius:12px;
            padding:12px;
            box-shadow: inset 0 0 0 1px rgba(255,122,47,0.06);
        }
        h1 { margin:0 0 6px; color:var(--accent); font-size:22px; }
        h2 { margin:0 0 10px; color:var(--accent); font-size:16px; }
        .muted { color:var(--muted); font-size:12px; }
        input, select {
            background:#0E0E13;
            color:var(--ink);
            border:1px solid var(--line);
            border-radius:9px;
            padding:8px;
        }
        textarea {
            background:#0E0E13;
            color:var(--ink);
            border:1px solid var(--line);
            border-radius:9px;
            padding:8px;
            min-height:78px;
            width:100%;
        }
        button {
            background:linear-gradient(180deg,#1d1a12,#14110c);
            color:var(--ink);
            border:1px solid rgba(212,168,87,0.45);
            border-radius:9px;
            padding:8px 10px;
            cursor:pointer;
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        button:hover {
            border-color:var(--accent);
            box-shadow: 0 0 0 1px rgba(212,168,87,0.22), 0 0 12px rgba(255,122,47,0.14);
        }
        pre { margin:0; max-height:360px; overflow:auto; white-space:pre-wrap; word-break:break-word; background:#0d1621; border:1px solid var(--line); border-radius:10px; padding:10px; font-size:12px; }
        .agent-item { border:1px solid var(--line); border-radius:9px; padding:8px; margin-bottom:6px; background:#132131; }
        .pill { display:inline-block; margin-left:8px; border-radius:999px; padding:1px 8px; border:1px solid var(--line); font-size:11px; }
        .pill.online { color:var(--ok); border-color:var(--ok); }
        .pill.warning, .pill.stale { color:var(--warn); border-color:var(--warn); }
        .pill.offline, .pill.critical { color:var(--bad); border-color:var(--bad); }
        .view-panel { display:none; }
        .view-panel.active { display:block; }
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
            <h1>BossForgeOS</h1>
            <div class="muted">Control Hall</div>
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
            <button class="nav-btn" data-view="view_iconforge" onclick="switchView('view_iconforge')" style="color:#ffb27d; font-weight:bold;">IconForge Studio</button>
            <button class="nav-btn" data-view="view_discovery" onclick="switchView('view_discovery')">Discovery Map</button>
            <button class="nav-btn" data-view="view_security" onclick="switchView('view_security')">Security</button>
            <button class="nav-btn" data-view="view_sounds" onclick="switchView('view_sounds')" style="color:#39ff14; font-weight:bold;">Sounds</button>
            <div class="group-label">Diagnostics</div>
            <button class="nav-btn" data-view="view_diagnostics" onclick="switchView('view_diagnostics')" style="color:#f17171; font-weight:bold;">Diagnostics</button>
        </aside>

        <main class="wrap">
            <section class="card">
                <h1>BossForgeOS Control Hall</h1>
                <div class="muted">Panels open in center. Pin any active panel to always-on-top desktop overlay.</div>
                <div class="row" style="margin-top:8px;">
                    <button id="pin_toggle" onclick="togglePinCurrentView()">Pin Current View</button>
                    <button onclick="clearPinnedView()">Unpin</button>
                    <span id="pin_note" class="pin-note">No desktop pin active</span>
                </div>
                <button class="anvil-btn" onclick="launchAnvilShuttle()">Launch Anvil Secured Shuttle</button>
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
            </section>

            <section id="view_status" class="card view-panel"><h2>Agent Status</h2><div id="agents" class="muted">Loading...</div></section>
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
                <pre id="sound_events">Open this panel to load sound status.</pre>
                <div class="row">
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="saveSoundScheme()">Save Scheme</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="loadSoundScheme()">Load Scheme</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="createNewScheme()">Create New Scheme</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="exportSoundforgeBundle()">Export Bundle</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="showImportBundleDialog()">Import Bundle</button>
                </div>
                <input type="file" id="sound_scheme_file" style="display:none;" accept=".json,.soundstage" onchange="handleSchemeFile(event)" />
                <input type="file" id="soundforge_bundle_file" style="display:none;" accept=".B4Gsoundforge,.B4Gsoundstage,application/zip" onchange="handleImportBundle(event)" />
                <div id="sound_scheme_status" class="muted" style="margin-top:10px;"></div>
                <div id="soundforge_schemes_list" class="muted" style="margin-top:10px;"></div>
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
                    <div class="muted" style="margin-bottom:8px;">Guided builder for quick agent creation.</div>
                    <div class="row">
                        <input id="wizard_name" placeholder="agent name" />
                        <select id="wizard_endpoint"></select>
                        <input id="wizard_role_focus" placeholder="what should this agent do?" />
                    </div>
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
                        </div>
                        <div id="wizard_icon_status" class="muted" style="margin-top:6px;">Using default icon.</div>
                    </div>
                    <div class="row">
                        <label class="muted" style="display:flex; align-items:center; gap:6px;">
                            <input id="wizard_encrypt_profile" type="checkbox" checked /> Encrypt profile via BossGate
                        </label>
                        <button onclick="buildWizardDraft()">Build Draft In Advanced</button>
                        <button onclick="createWizardAgent()">Create From Wizard</button>
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
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="maker_encrypt_profile" type="checkbox" checked /> Encrypt profile</label>
                        <button onclick="createAgentProfile()">Create/Update</button>
                    </div>
                    <pre id="maker_validation" class="muted">Role-aware validation ready.</pre>
                </div>

                <div class="row">
                    <select id="maker_agent_select"></select>
                    <input id="maker_task" placeholder="task for selected agent" />
                    <select id="maker_override_endpoint"></select>
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
                <pre id="maker_result">No agent operation yet.</pre>
            </section>

            <section id="view_iconforge" class="card view-panel">
                <h2 style="color:#ffb27d;">IconForge Studio</h2>
                <div class="muted" style="margin-bottom:8px;">Full-center icon editor for painting, importing, FX, and multi-size .ico export.</div>
                <div class="row" style="align-items:flex-start;">
                    <canvas id="icon_studio_canvas" width="256" height="256" style="width:256px; height:256px; border:1px solid #3c4559; border-radius:10px; background:linear-gradient(45deg, rgba(255,255,255,0.06) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.06) 75%), linear-gradient(45deg, rgba(255,255,255,0.06) 25%, transparent 25%, transparent 75%, rgba(255,255,255,0.06) 75%); background-size:16px 16px; background-position:0 0, 8px 8px; cursor:crosshair;"></canvas>
                    <div style="display:grid; gap:8px; min-width:340px;">
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
                            <select id="icon_studio_target">
                                <option value="wizard">apply to wizard</option>
                                <option value="advanced" selected>apply to advanced</option>
                                <option value="both">apply to both</option>
                            </select>
                        </div>
                        <div class="row">
                            <button onclick="triggerIconStudioImport()">Import Image</button>
                            <button onclick="iconStudioUndoStroke()">Undo</button>
                            <button onclick="iconStudioClearCanvas()">Clear</button>
                            <button onclick="iconStudioFillBackground()">Fill</button>
                            <input id="icon_studio_import_file" type="file" style="display:none;" accept=".png" onchange="handleIconStudioImport(event)" />
                        </div>
                        <div class="row">
                            <button onclick="applyIconStudioFx('grayscale')">FX: Grayscale</button>
                            <button onclick="applyIconStudioFx('invert')">FX: Invert</button>
                            <button onclick="applyIconStudioFx('contrast')">FX: Contrast+</button>
                            <button onclick="applyIconStudioFx('soften')">FX: Soften</button>
                        </div>
                        <div class="row">
                            <button onclick="saveIconStudioDraft()">Save Draft</button>
                            <button onclick="loadIconStudioDraft()">Load Draft</button>
                            <button onclick="clearIconStudioDraft()">Clear Draft</button>
                            <button onclick="downloadIconStudioPng()">Download PNG</button>
                        </div>
                        <div class="row">
                            <select id="icon_studio_anim_preset">
                                <option value="pulse" selected>anim: pulse</option>
                                <option value="spin">anim: spin</option>
                                <option value="shimmer">anim: shimmer</option>
                            </select>
                            <input id="icon_studio_anim_seconds" type="number" min="1" max="12" step="1" value="3" placeholder="seconds" />
                            <input id="icon_studio_anim_fps" type="number" min="6" max="30" step="1" value="12" placeholder="fps" />
                            <button onclick="saveIconStudioAnimated()">Save Animated GIF</button>
                        </div>
                        <div class="row">
                            <button onclick="saveIconStudioIco()">Save .ico (16-256)</button>
                        </div>
                        <div id="icon_studio_status" class="muted">Studio ready.</div>
                    </div>
                </div>

                <div style="border:1px solid #2b2f3a; border-radius:10px; padding:10px; margin-top:12px;">
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
                        <button onclick="setIconForgeFromStudioIco()">Use Latest Studio ICO</button>
                        <button onclick="applyWindowsIconOverride()">Apply Icon Override</button>
                        <button onclick="refreshWindowsIconCache()">Refresh Icon Cache</button>
                    </div>
                    <div class="row">
                        <input id="iconforge_restore_key" placeholder="backup key to restore" />
                        <button onclick="restoreWindowsIconOverride()">Restore Backup</button>
                        <button onclick="refreshIconForgeOps()">Refresh Backups</button>
                    </div>
                    <div class="row">
                        <input id="iconforge_pack_export_dir" placeholder="export pack directory path" />
                        <button onclick="exportIconForgePack()">Export Icon Pack</button>
                    </div>
                    <div class="row">
                        <input id="iconforge_pack_import_source" placeholder="import pack source (dir or icon_set_manifest.json path)" />
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="iconforge_pack_apply" type="checkbox" checked /> apply changes</label>
                        <label class="muted" style="display:flex; align-items:center; gap:6px;"><input id="iconforge_pack_refresh" type="checkbox" checked /> refresh cache</label>
                        <button onclick="importIconForgePack()">Import Icon Pack</button>
                    </div>
                    <pre id="iconforge_ops_result">No icon operations yet.</pre>
                    <pre id="iconforge_backups">No backups loaded.</pre>
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
        let previousOsState = null;
        let busLiveTimer = null;
        let iconStudioCtx = null;
        let iconStudioDrawing = false;
        let iconStudioUndo = [];
        let iconStudioBooted = false;
        const ICON_STUDIO_DRAFT_KEY = 'bossforge.iconforge.studio.v1';

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
            const data = await fetchJsonWithTimeout('/api/model/travel/discover?timeout=5&assistance_only=' + (assistanceOnly ? 'true' : 'false'), 5000);
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
            if (viewId === 'view_iconforge') refreshIconForgeOps();
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

        function applyUrlLaunchContext() {
            const params = new URLSearchParams(window.location.search || '');
            const requestedView = (params.get('view') || '').trim();
            if (requestedView && document.getElementById(requestedView)) {
                switchView(requestedView);
            }

            const openIcon = (params.get('open_icon') || '').trim();
            if (!openIcon) return;

            if (currentView !== 'view_iconforge') {
                switchView('view_iconforge');
            }

            const iconPathInput = document.getElementById('iconforge_icon_path');
            if (iconPathInput) {
                iconPathInput.value = openIcon;
            }

            const baseName = openIcon.split(/[\\/]/).pop() || '';
            const iconStem = baseName.replace(/\.[^.]+$/, '').trim();
            const studioName = document.getElementById('icon_studio_name');
            if (studioName && iconStem) {
                studioName.value = iconStem;
            }

            setIconStudioStatus('Explorer selection loaded: ' + openIcon);
        }

        document.addEventListener('keydown', (event) => {
            if (!(event.ctrlKey || event.metaKey)) return;
            if (String(event.key || '').toLowerCase() !== 's') return;
            if (currentView !== 'view_iconforge') return;
            event.preventDefault();
            saveIconStudioIco();
        });

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

        function iconStudioBuildDraftPayload() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return null;
            return {
                image_data: canvas.toDataURL('image/png'),
                icon_name: (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim(),
                target: (document.getElementById('icon_studio_target')?.value || 'advanced').trim(),
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
            if (!canvas || !iconStudioCtx) return;
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
                iconStudioCtx.clearRect(0, 0, canvas.width, canvas.height);
                iconStudioCtx.drawImage(img, 0, 0, canvas.width, canvas.height);

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
                if (targetEl && payload.target) targetEl.value = String(payload.target);
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
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas || !iconStudioCtx) return;
            const frame = iconStudioCtx.getImageData(0, 0, canvas.width, canvas.height);
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
            if (!iconStudioCtx) return;
            const stroke = iconStudioCurrentStroke();
            iconStudioCtx.save();
            iconStudioCtx.lineCap = 'round';
            iconStudioCtx.lineJoin = 'round';
            iconStudioCtx.lineWidth = stroke.size;
            iconStudioCtx.globalCompositeOperation = stroke.eraser ? 'destination-out' : 'source-over';
            iconStudioCtx.strokeStyle = stroke.color;
            iconStudioCtx.beginPath();
            iconStudioCtx.moveTo(from.x, from.y);
            iconStudioCtx.lineTo(to.x, to.y);
            iconStudioCtx.stroke();
            iconStudioCtx.restore();
        }

        function initIconForgeStudio() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            if (iconStudioBooted) return;
            iconStudioCtx = canvas.getContext('2d', { willReadFrequently: true });
            if (!iconStudioCtx) return;
            iconStudioBooted = true;
            iconStudioCtx.clearRect(0, 0, canvas.width, canvas.height);
            iconStudioCtx.fillStyle = 'rgba(0,0,0,0)';
            iconStudioCtx.fillRect(0, 0, canvas.width, canvas.height);

            const slider = document.getElementById('icon_studio_size');
            const label = document.getElementById('icon_studio_size_label');
            if (slider && label) {
                const sync = () => {
                    label.textContent = String(parseInt(slider.value || '10', 10)) + 'px';
                };
                slider.addEventListener('input', sync);
                sync();
            }

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
            if (!file || !canvas || !iconStudioCtx) return;
            try {
                const objectUrl = URL.createObjectURL(file);
                const img = new Image();
                await new Promise((resolve, reject) => {
                    img.onload = () => resolve();
                    img.onerror = () => reject(new Error('image load failed'));
                    img.src = objectUrl;
                });
                iconStudioPushUndo();
                iconStudioCtx.clearRect(0, 0, canvas.width, canvas.height);
                const scale = Math.min(canvas.width / img.width, canvas.height / img.height);
                const drawW = Math.max(1, Math.floor(img.width * scale));
                const drawH = Math.max(1, Math.floor(img.height * scale));
                const offX = Math.floor((canvas.width - drawW) / 2);
                const offY = Math.floor((canvas.height - drawH) / 2);
                iconStudioCtx.drawImage(img, offX, offY, drawW, drawH);
                URL.revokeObjectURL(objectUrl);
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
            iconStudioCtx.putImageData(frame, 0, 0);
            saveIconStudioDraft(false);
            setIconStudioStatus('Undo applied.');
        }

        function iconStudioClearCanvas() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas || !iconStudioCtx) return;
            iconStudioPushUndo();
            iconStudioCtx.clearRect(0, 0, canvas.width, canvas.height);
            saveIconStudioDraft(false);
            setIconStudioStatus('Canvas cleared.');
        }

        function iconStudioFillBackground() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas || !iconStudioCtx) return;
            const color = document.getElementById('icon_studio_color')?.value || '#1d3557';
            iconStudioPushUndo();
            iconStudioCtx.save();
            iconStudioCtx.globalCompositeOperation = 'source-over';
            iconStudioCtx.fillStyle = color;
            iconStudioCtx.fillRect(0, 0, canvas.width, canvas.height);
            iconStudioCtx.restore();
            saveIconStudioDraft(false);
            setIconStudioStatus('Background filled.');
        }

        function applyIconStudioFx(kind) {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas || !iconStudioCtx) return;
            iconStudioPushUndo();
            const image = iconStudioCtx.getImageData(0, 0, canvas.width, canvas.height);
            const data = image.data;
            for (let i = 0; i < data.length; i += 4) {
                const r = data[i];
                const g = data[i + 1];
                const b = data[i + 2];
                if (kind === 'grayscale') {
                    const y = Math.round(0.299 * r + 0.587 * g + 0.114 * b);
                    data[i] = y;
                    data[i + 1] = y;
                    data[i + 2] = y;
                } else if (kind === 'invert') {
                    data[i] = 255 - r;
                    data[i + 1] = 255 - g;
                    data[i + 2] = 255 - b;
                } else if (kind === 'contrast') {
                    const c = 36;
                    const factor = (259 * (c + 255)) / (255 * (259 - c));
                    data[i] = Math.max(0, Math.min(255, Math.round(factor * (r - 128) + 128)));
                    data[i + 1] = Math.max(0, Math.min(255, Math.round(factor * (g - 128) + 128)));
                    data[i + 2] = Math.max(0, Math.min(255, Math.round(factor * (b - 128) + 128)));
                } else if (kind === 'soften') {
                    data[i] = Math.round((r + 255) / 2);
                    data[i + 1] = Math.round((g + 255) / 2);
                    data[i + 2] = Math.round((b + 255) / 2);
                }
            }
            iconStudioCtx.putImageData(image, 0, 0);
            saveIconStudioDraft(false);
            setIconStudioStatus('Applied FX: ' + kind);
        }

        async function saveIconStudioIco() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            const iconName = (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim();
            const target = (document.getElementById('icon_studio_target')?.value || 'advanced').trim();
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
            setIconStudioStatus('Saved icon: ' + iconPath + ' (sizes: 16,24,32,48,64,128,256)');
        }

        async function saveIconStudioAnimated() {
            const canvas = document.getElementById('icon_studio_canvas');
            if (!canvas) return;
            const iconName = (document.getElementById('icon_studio_name')?.value || 'agent_forge_icon').trim();
            const target = (document.getElementById('icon_studio_target')?.value || 'advanced').trim();
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
            setIconStudioStatus('Animated saved: ' + gifPath + ' | ICO fallback: ' + icoPath);
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
            const marker = '\n\nPersonality Wrapper (';
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
            if (!useWizard) syncAdvancedPolicyAwareness();
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
            syncAdvancedPolicyAwareness();
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

        function renderSnapshotDashboard(snapshot) {
            const root = document.getElementById('snapshot_dashboard');
            const warningsRoot = document.getElementById('snapshot_warnings');
            if (!root || !warningsRoot) return;

            const system = (snapshot && snapshot.system && typeof snapshot.system === 'object') ? snapshot.system : {};
            const memory = (system.memory && typeof system.memory === 'object') ? system.memory : {};
            const swap = (system.swap && typeof system.swap === 'object') ? system.swap : {};
            const disk = (snapshot && snapshot.disk && typeof snapshot.disk === 'object') ? snapshot.disk : {};
            const gpu = (snapshot && snapshot.gpu_vram && Array.isArray(snapshot.gpu_vram.gpus)) ? snapshot.gpu_vram.gpus[0] : null;

            const gauges = [
                {
                    label: 'CPU',
                    percent: percentValue(system.cpu_percent),
                    detail: String(Number.isFinite(Number(system.cpu_percent)) ? Number(system.cpu_percent).toFixed(1) : '0.0') + '%',
                },
                {
                    label: 'RAM',
                    percent: percentValue(memory.percent),
                    detail: (memory.used_gb ?? '?') + ' / ' + (memory.total_gb ?? '?') + ' GB',
                },
                {
                    label: 'Disk',
                    percent: percentValue(disk.percent),
                    detail: (disk.used_gb ?? '?') + ' / ' + (disk.total_gb ?? '?') + ' GB',
                },
                {
                    label: 'Swap',
                    percent: percentValue(swap.percent),
                    detail: (swap.used_gb ?? '?') + ' / ' + (swap.total_gb ?? '?') + ' GB',
                },
            ];

            if (gpu) {
                gauges.push({
                    label: 'GPU VRAM',
                    percent: percentValue(gpu.percent),
                    detail: (gpu.used_gb ?? '?') + ' / ' + (gpu.total_gb ?? '?') + ' GB',
                });
            }

            root.innerHTML = gauges.map((item) => {
                const p = percentValue(item.percent);
                const tone = gaugeTone(p);
                const sweepClass = snapshotGaugeBooted ? '' : ' sweep';
                const pulse = pulseClass(p);
                return '<div class="gauge-card">'
                    + '<div class="gauge-head"><strong>' + htmlEscape(item.label) + '</strong><span class="muted">' + p.toFixed(1) + '%</span></div>'
                    + '<div class="tachometer' + sweepClass + pulse + '" style="--pct:' + p.toFixed(1) + ';--tone:' + tone + ';">'
                    + '<div class="halo"></div>'
                    + '<svg viewBox="0 0 100 60" aria-hidden="true">'
                    + '<path class="arc-bg" pathLength="100" d="M 10 50 A 40 40 0 0 1 90 50"></path>'
                    + '<path class="arc-fg" pathLength="100" d="M 10 50 A 40 40 0 0 1 90 50"></path>'
                    + '</svg>'
                    + '<div class="ticks"></div>'
                    + '</div>'
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
            } else {
                document.getElementById('agents').innerHTML = '<div class="muted">Status unavailable.</div>';
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
        syncWizardStateMachinePreview();
        applySelectedStateMachineTemplate();
        refresh();
        listSoundforgeSchemes();
        setInterval(refresh, 4000);
        setInterval(refreshPinState, 3000);
    </script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


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
    pending_path = bus.state / "runeforge_pending_approval.json"
    runeforge_state_path = bus.state / "runeforge.json"

    pending = None
    if pending_path.exists():
        try:
            payload = json.loads(pending_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                pending = payload
        except (OSError, json.JSONDecodeError):
            pending = {"error": "invalid pending approval state"}

    last_report = None
    if runeforge_state_path.exists():
        try:
            state = json.loads(runeforge_state_path.read_text(encoding="utf-8"))
            if isinstance(state, dict):
                if isinstance(state.get("report"), dict):
                    last_report = state.get("report")
                elif isinstance(state.get("execution"), dict) and isinstance(state.get("execution", {}).get("report"), dict):
                    last_report = state.get("execution", {}).get("report")
        except (OSError, json.JSONDecodeError):
            pass

    if last_report is None:
        events = bus.read_latest_events(limit=120)
        for item in events:
            if str(item.get("source", "")).strip() != "runeforge":
                continue
            event_name = str(item.get("event", "")).strip()
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            if event_name in {"sentinel_plan_approval_result", "sentinel_recommendations_applied", "os_action_approval_result"}:
                if isinstance(data.get("report"), dict):
                    last_report = data.get("report")
                elif isinstance(data.get("execution"), dict) and isinstance(data.get("execution", {}).get("report"), dict):
                    last_report = data.get("execution", {}).get("report")
                else:
                    last_report = {
                        "action_type": event_name,
                        "ok": bool(data.get("ok", True)),
                    }
                break

    return jsonify({"ok": True, "pending_approval": pending, "last_report": last_report})


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
    path = bus.state / "model_endpoints.json"
    if not path.exists():
        return jsonify({"endpoints": {}})
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return jsonify({"endpoints": {}})
        return jsonify({"endpoints": data})
    except (OSError, json.JSONDecodeError):
        return jsonify({"endpoints": {}})


@app.get("/api/model/agents")
def model_agents():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    return jsonify({"agents": gateway.list_agent_profiles()})


@app.post("/api/model/agents/create")
def model_agents_create():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    endpoint = str(payload.get("endpoint", "")).strip()
    system = str(payload.get("system", "You are a helpful specialist agent."))
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 900))
    agent_class = str(payload.get("agent_class", "prime")).strip().lower()
    has_llm_raw = payload.get("has_llm")
    has_llm = bool(has_llm_raw) if isinstance(has_llm_raw, bool) else None
    bossgate_enabled_raw = payload.get("bossgate_enabled")
    bossgate_enabled = True if bossgate_enabled_raw is None else bool(bossgate_enabled_raw)
    encrypt_profile_raw = payload.get("encrypt_profile")
    encrypt_profile = True if encrypt_profile_raw is None else bool(encrypt_profile_raw)
    agent_type = str(payload.get("agent_type", "")).strip().lower() or None
    rank = str(payload.get("rank", "")).strip().lower() or None
    skills_raw = payload.get("skills")
    skills = skills_raw if isinstance(skills_raw, list) else None
    sigils_raw = payload.get("sigils")
    sigils = sigils_raw if isinstance(sigils_raw, list) else None
    dispatch_policy_raw = payload.get("dispatch_policy")
    dispatch_policy = dispatch_policy_raw if isinstance(dispatch_policy_raw, dict) else None
    personality_wrapper_raw = payload.get("personality_wrapper")
    personality_wrapper = personality_wrapper_raw if isinstance(personality_wrapper_raw, dict) else None
    system_wrapper_raw = payload.get("system_wrapper")
    system_wrapper = system_wrapper_raw if isinstance(system_wrapper_raw, dict) else None
    instructions_raw = payload.get("instructions")
    instructions = instructions_raw if isinstance(instructions_raw, dict) else None
    state_machine_raw = payload.get("state_machine")
    state_machine = state_machine_raw if isinstance(state_machine_raw, dict) else None
    custom_icon_path = str(payload.get("custom_icon_path", "")).strip() or None

    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.create_agent_profile(
        name,
        endpoint,
        system,
        temperature,
        max_tokens,
        agent_class=agent_class,
        has_llm=has_llm,
        bossgate_enabled=bossgate_enabled,
        encrypt_profile=encrypt_profile,
        agent_type=agent_type,
        rank=rank,
        skills=skills,
        sigils=sigils,
        dispatch_policy=dispatch_policy,
        personality_wrapper=personality_wrapper,
        system_wrapper=system_wrapper,
        instructions=instructions,
        state_machine=state_machine,
        custom_icon_path=custom_icon_path,
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/agentforge/icon/upload")
def agentforge_icon_upload():
    from core.icons.icon_forge import IconForge

    uploaded = request.files.get("icon")
    if uploaded is None:
        return jsonify({"ok": False, "message": "icon file is required"}), 400

    original_name = secure_filename(uploaded.filename or "")
    if not original_name:
        return jsonify({"ok": False, "message": "icon file name is required"}), 400

    source_ext = Path(original_name).suffix.lower()
    allowed = {".png"}
    if source_ext not in allowed:
        return jsonify({"ok": False, "message": "unsupported file type; use .png"}), 400

    hint = str(request.form.get("icon_name", "agent_icon")).strip()
    stem = _safe_icon_stem(hint)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = PROJECT_ROOT / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)

    try:
        source_path = icon_dir / f"{stem}_{suffix}{source_ext}"
        final_path = icon_dir / f"{stem}_{suffix}.ico"
        uploaded.save(source_path)

        forge = IconForge(PROJECT_ROOT)
        result = forge.create_icon_from_image(str(source_path), str(final_path))
        if source_path.exists():
            source_path.unlink(missing_ok=True)
        if not result.get("ok"):
            return jsonify({"ok": False, "message": str(result.get("message", "icon conversion failed"))}), 400
        return jsonify({"ok": True, "icon": _to_project_relpath(final_path), "message": "icon uploaded and converted"})
    except Exception as exc:
        return jsonify({"ok": False, "message": f"icon upload failed: {exc}"}), 500


@app.post("/api/agentforge/icon/create")
def agentforge_icon_create():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    icon_name = str(payload.get("icon_name", "agent_icon")).strip()
    label = str(payload.get("label", "AG")).strip() or "AG"
    background = str(payload.get("background", "#1d3557")).strip() or "#1d3557"
    foreground = str(payload.get("foreground", "#f1faee")).strip() or "#f1faee"

    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = PROJECT_ROOT / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)
    final_path = icon_dir / f"{stem}_{suffix}.ico"

    try:
        forge = IconForge(PROJECT_ROOT)
        result = forge.create_icon_from_text(
            text=label,
            output_ico=str(final_path),
            background=background,
            foreground=foreground,
        )
        if not result.get("ok"):
            return jsonify({"ok": False, "message": str(result.get("message", "icon creation failed"))}), 400
        return jsonify({"ok": True, "icon": _to_project_relpath(final_path), "message": "icon created"})
    except Exception as exc:
        return jsonify({"ok": False, "message": f"icon creation failed: {exc}"}), 500


@app.post("/api/agentforge/icon/create_from_canvas")
def agentforge_icon_create_from_canvas():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    icon_name = str(payload.get("icon_name", "agent_icon")).strip()
    image_data = str(payload.get("image_data", "")).strip()
    if not image_data.startswith("data:image/png"):
        return jsonify({"ok": False, "message": "image_data must be a PNG data URL"}), 400

    comma_idx = image_data.find(",")
    if comma_idx <= 0:
        return jsonify({"ok": False, "message": "invalid image_data format"}), 400

    encoded = image_data[comma_idx + 1 :]
    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = PROJECT_ROOT / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)
    temp_png = icon_dir / f"{stem}_{suffix}_src.png"
    final_path = icon_dir / f"{stem}_{suffix}.ico"

    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return jsonify({"ok": False, "message": "image_data is not valid base64"}), 400

    try:
        temp_png.write_bytes(raw)
        forge = IconForge(PROJECT_ROOT)
        result = forge.create_icon_from_image(str(temp_png), str(final_path))
        if not result.get("ok"):
            return jsonify({"ok": False, "message": str(result.get("message", "icon creation failed"))}), 400
        return jsonify({"ok": True, "icon": _to_project_relpath(final_path), "message": "icon created"})
    except Exception as exc:
        return jsonify({"ok": False, "message": f"icon creation failed: {exc}"}), 500
    finally:
        if temp_png.exists():
            temp_png.unlink(missing_ok=True)


@app.post("/api/agentforge/icon/create_animated_from_canvas")
def agentforge_icon_create_animated_from_canvas():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    icon_name = str(payload.get("icon_name", "agent_icon")).strip()
    image_data = str(payload.get("image_data", "")).strip()
    preset = str(payload.get("preset", "pulse")).strip().lower()
    seconds = int(payload.get("seconds", 3))
    fps = int(payload.get("fps", 12))

    if not image_data.startswith("data:image/png"):
        return jsonify({"ok": False, "message": "image_data must be a PNG data URL"}), 400

    comma_idx = image_data.find(",")
    if comma_idx <= 0:
        return jsonify({"ok": False, "message": "invalid image_data format"}), 400

    encoded = image_data[comma_idx + 1 :]
    stem = _safe_icon_stem(icon_name)
    suffix = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    icon_dir = PROJECT_ROOT / "assets" / "icons" / "agents"
    icon_dir.mkdir(parents=True, exist_ok=True)
    temp_png = icon_dir / f"{stem}_{suffix}_anim_src.png"
    final_ico = icon_dir / f"{stem}_{suffix}.ico"
    final_gif = icon_dir / f"{stem}_{suffix}.gif"

    try:
        raw = base64.b64decode(encoded)
    except Exception:
        return jsonify({"ok": False, "message": "image_data is not valid base64"}), 400

    try:
        from PIL import Image, ImageEnhance
    except Exception:
        return jsonify({"ok": False, "message": "Pillow is required for animated export. Install with: pip install pillow"}), 400

    seconds = max(1, min(12, seconds))
    fps = max(6, min(30, fps))
    total_frames = max(8, min(360, seconds * fps))
    duration_ms = int(1000 / fps)

    try:
        temp_png.write_bytes(raw)
        base = Image.open(temp_png).convert("RGBA")
        w, h = base.size
        frames = []

        for idx in range(total_frames):
            t = idx / max(1, total_frames - 1)
            if preset == "spin":
                angle = 360.0 * t
                frame = base.rotate(angle, resample=Image.BICUBIC, expand=False)
            elif preset == "shimmer":
                frame = base.copy()
                overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                band_center = int((w * 1.5) * t) - (w // 4)
                for x in range(w):
                    dist = abs(x - band_center)
                    if dist > w // 5:
                        continue
                    alpha = max(0, 140 - int((dist / (w // 5 + 1)) * 140))
                    for y in range(h):
                        overlay.putpixel((x, y), (255, 255, 255, alpha))
                frame = Image.alpha_composite(frame, overlay)
            else:
                pulse = 0.88 + 0.20 * (0.5 + 0.5 * math.sin(2.0 * math.pi * t))
                nw = max(8, int(w * pulse))
                nh = max(8, int(h * pulse))
                resized = base.resize((nw, nh), resample=Image.BICUBIC)
                frame = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                frame.paste(resized, ((w - nw) // 2, (h - nh) // 2), resized)
                frame = ImageEnhance.Brightness(frame).enhance(1.05)
            frames.append(frame)

        if not frames:
            return jsonify({"ok": False, "message": "failed to build animated frames"}), 400

        frames[0].save(
            final_gif,
            format="GIF",
            save_all=True,
            append_images=frames[1:],
            loop=0,
            duration=duration_ms,
            disposal=2,
            transparency=0,
        )

        forge = IconForge(PROJECT_ROOT)
        ico_result = forge.create_icon_from_image(str(temp_png), str(final_ico))
        if not ico_result.get("ok"):
            return jsonify({"ok": False, "message": str(ico_result.get("message", "ico fallback creation failed"))}), 400

        return jsonify(
            {
                "ok": True,
                "animated": _to_project_relpath(final_gif),
                "icon": _to_project_relpath(final_ico),
                "preset": preset,
                "frames": total_frames,
                "fps": fps,
                "seconds": seconds,
                "message": "animated gif + ico fallback created",
            }
        )
    except Exception as exc:
        return jsonify({"ok": False, "message": f"animated export failed: {exc}"}), 500
    finally:
        if temp_png.exists():
            temp_png.unlink(missing_ok=True)


@app.get("/api/iconforge/backups")
def iconforge_backups():
    from core.icons.icon_forge import IconForge

    try:
        forge = IconForge(PROJECT_ROOT)
        return jsonify({"ok": True, "items": forge.list_backups()})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc), "items": {}}), 500


@app.post("/api/iconforge/apply")
def iconforge_apply():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    target_type = str(payload.get("target_type", "folder")).strip().lower()
    target = str(payload.get("target", "")).strip()
    icon = str(payload.get("icon", "")).strip()
    if not target or not icon:
        return jsonify({"ok": False, "message": "target and icon are required"}), 400

    icon_path = Path(icon)
    if not icon_path.is_absolute():
        icon_path = (PROJECT_ROOT / icon_path).resolve()

    forge = IconForge(PROJECT_ROOT)
    if target_type == "folder":
        result = forge.set_folder_icon(target, str(icon_path))
    elif target_type == "shortcut":
        result = forge.set_shortcut_icon(target, str(icon_path))
    elif target_type == "file_extension":
        result = forge.set_file_extension_icon(target, str(icon_path))
    elif target_type == "application":
        result = forge.set_application_icon(target, str(icon_path))
    elif target_type == "drive":
        result = forge.set_drive_icon(target, str(icon_path))
    else:
        return jsonify({"ok": False, "message": f"unsupported target_type: {target_type}"}), 400

    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/iconforge/refresh_cache")
def iconforge_refresh_cache():
    from core.icons.icon_forge import IconForge

    forge = IconForge(PROJECT_ROOT)
    result = forge.refresh_icon_cache()
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/iconforge/restore")
def iconforge_restore():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    backup_key = str(payload.get("backup_key", "")).strip()
    if not backup_key:
        return jsonify({"ok": False, "message": "backup_key is required"}), 400
    forge = IconForge(PROJECT_ROOT)
    result = forge.restore(backup_key)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/iconforge/pack/export")
def iconforge_pack_export():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    output_dir = str(payload.get("output_dir", "")).strip()
    if not output_dir:
        return jsonify({"ok": False, "message": "output_dir is required"}), 400

    forge = IconForge(PROJECT_ROOT)
    result = forge.export_icon_set(output_dir)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/iconforge/pack/import")
def iconforge_pack_import():
    from core.icons.icon_forge import IconForge

    payload = request.get_json(force=True, silent=True) or {}
    source = str(payload.get("source", "")).strip()
    apply_changes = bool(payload.get("apply_changes", True))
    refresh_cache = bool(payload.get("refresh_cache", False))
    if not source:
        return jsonify({"ok": False, "message": "source is required"}), 400

    forge = IconForge(PROJECT_ROOT)
    result = forge.import_icon_set(source=source, apply_changes=apply_changes, refresh_cache=refresh_cache)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/triage")
def model_agents_triage():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    from core.schemas.agent_schema import infer_incident_domains, rank_agents_for_incident

    payload = request.get_json(force=True, silent=True) or {}
    incident = payload.get("incident") if isinstance(payload.get("incident"), dict) else {}
    weights_raw = payload.get("weights")
    weights = weights_raw if isinstance(weights_raw, dict) else None

    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    profiles = gateway.list_agent_profiles()
    candidates = []
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        item = dict(profile)
        item.setdefault("id", str(name).strip().lower())
        item.setdefault("name", str(name).strip().lower())
        candidates.append(item)

    ranked = rank_agents_for_incident(incident=incident, agent_profiles=candidates, weights=weights)
    return jsonify(
        {
            "ok": True,
            "incident_inference": infer_incident_domains(incident),
            "ranked_candidates": ranked,
            "candidate_count": len(candidates),
        }
    )


@app.post("/api/model/agents/delete")
def model_agents_delete():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.delete_agent_profile(name)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/run")
def model_agents_run():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    task = str(payload.get("task", "")).strip()
    endpoint = str(payload.get("endpoint", "")).strip()
    memory_context = payload.get("memory_context") if isinstance(payload.get("memory_context"), dict) else {}
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.run_agent_profile(name, task, endpoint, memory_context=memory_context)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/agents/memory")
def model_agents_memory():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    name = str(request.args.get("name", "")).strip()
    limit = int(request.args.get("limit", "25"))
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.recall_agent_memory(name=name, limit=limit)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/travel/discover")
def model_travel_discover():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    timeout = int(request.args.get("timeout", "5"))
    assistance_only = str(request.args.get("assistance_only", "false")).strip().lower() in {"1", "true", "yes", "on"}
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.discover_travel_targets(timeout=timeout, assistance_only=assistance_only)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/travel/validate")
def model_travel_validate():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    payload = request.get_json(force=True, silent=True) or {}
    destination = str(payload.get("destination", "")).strip()
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.validate_transfer_target(destination=destination)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/assistance")
def model_agents_assistance_set():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    requested = bool(payload.get("requested", True))
    reason = str(payload.get("reason", "")).strip()
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.set_agent_assistance_request(name=name, requested=requested, reason=reason)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/agents/assistance")
def model_agents_assistance_list():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.list_assistance_requests()
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/model/agents/locations")
def model_agents_locations():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    refresh = str(request.args.get("refresh", "false")).strip().lower() in {"1", "true", "yes", "on"}
    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.list_owned_agent_locations(refresh=refresh)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/chat")
def model_chat():
    from core.agents.model_gateway_agent import ModelGatewayAgent
    payload = request.get_json(force=True, silent=True) or {}
    endpoint = str(payload.get("endpoint", "")).strip()
    prompt = str(payload.get("prompt", "")).strip()
    system = str(payload.get("system", "You are BossForgeOS assistant."))
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 900))

    if not endpoint or not prompt:
        return jsonify({"ok": False, "message": "endpoint and prompt are required"}), 400

    gateway = ModelGatewayAgent(interval_seconds=5, enable_presence_broadcast=False)
    result = gateway.invoke_endpoint(endpoint, prompt, system, temperature, max_tokens)
    return jsonify(result)


@app.get("/api/security/state")
def security_state():
    path = bus.state / "security_sentinel.json"
    if not path.exists():
        return jsonify({"ok": True, "status": "idle", "findings": []})
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {"ok": False, "message": "invalid security state", "findings": []}
    if not isinstance(payload, dict):
        payload = {"ok": False, "message": "invalid security state", "findings": []}
    payload.setdefault("findings", [])
    return jsonify(payload)


@app.post("/api/security/scan")
def security_scan():
    payload = request.get_json(force=True, silent=True) or {}
    path = str(payload.get("path", "")).strip()
    agent = SecuritySentinelAgent(interval_seconds=20)
    result = agent.scan_workspace(path)
    agent.bus.emit_event("security_sentinel", "manual:scan_workspace", result)
    agent.bus.write_state("security_sentinel", {"service": "security_sentinel", "pid": os.getpid(), "last_command": "scan_workspace", **result})
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.get("/api/security/secrets")
def security_secrets():
    agent = SecuritySentinelAgent(interval_seconds=20)
    result = agent.list_secrets()
    return jsonify(result)


@app.post("/api/security/policy/set")
def security_policy_set():
    payload = request.get_json(force=True, silent=True) or {}
    agent_name = str(payload.get("agent", "")).strip()
    actions = payload.get("actions") if isinstance(payload.get("actions"), list) else []
    agent = SecuritySentinelAgent(interval_seconds=20)
    result = agent.set_policy(agent_name, [str(a) for a in actions])
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/security/policy/check")
def security_policy_check():
    payload = request.get_json(force=True, silent=True) or {}
    agent_name = str(payload.get("agent", "")).strip()
    action = str(payload.get("action", "")).strip()
    agent = SecuritySentinelAgent(interval_seconds=20)
    result = agent.check_policy(agent_name, action)
    return jsonify(result)


def _pin_overlay_is_running() -> bool:
    global PIN_OVERLAY_PROCESS
    if PIN_OVERLAY_PROCESS is None:
        return False


    def _safe_icon_stem(value: str) -> str:
        cleaned = secure_filename(str(value or "").strip())
        if not cleaned:
            return "agent_icon"
        stem = Path(cleaned).stem.replace("-", "_")
        stem = "".join(ch for ch in stem if ch.isalnum() or ch == "_").strip("_")
        return (stem[:64] or "agent_icon").lower()


    def _to_project_relpath(path: Path) -> str:
        try:
            return str(path.resolve().relative_to(PROJECT_ROOT.resolve())).replace("\\", "/")
        except Exception:
            return str(path).replace("\\", "/")
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
    if PIN_OVERLAY_PROCESS is not None and PIN_OVERLAY_PROCESS.poll() is not None:
        PIN_OVERLAY_PROCESS = None
        PIN_OVERLAY_VIEW = ""
    return jsonify({"ok": True, "running": _pin_overlay_is_running(), "view": PIN_OVERLAY_VIEW, "alpha": PIN_OVERLAY_ALPHA})


@app.post("/api/pin/launch")
def pin_launch():
    global PIN_OVERLAY_PROCESS, PIN_OVERLAY_VIEW, PIN_OVERLAY_ALPHA
    payload = request.get_json(force=True, silent=True) or {}
    view = str(payload.get("view", "")).strip() or "view_status"
    try:
        alpha = float(payload.get("alpha", PIN_OVERLAY_ALPHA))
    except (TypeError, ValueError):
        alpha = PIN_OVERLAY_ALPHA
    alpha = max(0.35, min(1.0, alpha))

    overlay_path = Path(__file__).resolve().parent / "pin_overlay.py"
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


def _health_from_timestamp(ts: str | None) -> str:
    if not ts:
        return "offline"
    try:
        then = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return "offline"
    delta = (datetime.now(timezone.utc) - then).total_seconds()
    if delta <= 60:
        return "online"
    if delta <= 300:
        return "stale"
    return "offline"


def _model_agent_state_key(name: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in name.strip().lower())
    return f"model_agent_{safe}"


def read_agent_state() -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}

    dynamic_agents: dict[str, str] = {}
    dynamic_meta: dict[str, dict[str, str]] = {}
    profiles_path = bus.state / "model_agents.json"
    if profiles_path.exists():
        try:
            profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
            if isinstance(profiles, dict):
                endpoints = {}
                endpoints_path = bus.state / "model_endpoints.json"
                if endpoints_path.exists():
                    try:
                        raw_eps = json.loads(endpoints_path.read_text(encoding="utf-8"))
                        if isinstance(raw_eps, dict):
                            endpoints = raw_eps
                    except (OSError, json.JSONDecodeError):
                        endpoints = {}

                for name, profile in profiles.items():
                    key = str(name).strip().lower()
                    if key:
                        state_key = _model_agent_state_key(key)
                        dynamic_agents[state_key] = f"Model Agent: {key}"
                        endpoint = ""
                        provider = ""
                        if isinstance(profile, dict):
                            endpoint = str(profile.get("endpoint", "")).strip()
                        if endpoint and isinstance(endpoints, dict):
                            endpoint_cfg = endpoints.get(endpoint)
                            if isinstance(endpoint_cfg, dict):
                                provider = str(endpoint_cfg.get("provider", "")).strip()
                        dynamic_meta[state_key] = {"endpoint": endpoint, "provider": provider}
        except (OSError, json.JSONDecodeError):
            pass

    combined = dict(AGENT_STATUS)
    combined.update(dynamic_agents)

    for key, display in combined.items():
        state_file = bus.state / f"{key}.json"
        payload = {}
        if state_file.exists():
            try:
                payload = json.loads(state_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                payload = {}

        last_seen = payload.get("timestamp")
        meta = dynamic_meta.get(key, {})
        endpoint = str(payload.get("endpoint", "") or meta.get("endpoint", "")).strip()
        provider = str(meta.get("provider", "")).strip()
        result[key] = {
            "display_name": display,
            "health": _health_from_timestamp(last_seen),
            "last_seen": last_seen or "never",
            "endpoint": endpoint,
            "provider": provider,
        }
    return result


# === SoundForge Bundle Endpoints ===
import zipfile
import shutil

SOUNDFORGE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "soundforge_config.json")
LEGACY_SOUNDSTAGE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "soundstage_config.json")
SOUNDFORGE_SCHEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "core", "soundforge_schemes")
LEGACY_SOUNDSTAGE_SCHEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "core", "soundstage_schemes")
SOUNDFORGE_SOUNDS_DIR = os.path.join(SOUNDFORGE_SCHEMES_DIR, "sounds")
os.makedirs(SOUNDFORGE_SCHEMES_DIR, exist_ok=True)
os.makedirs(SOUNDFORGE_SOUNDS_DIR, exist_ok=True)

def _rewrite_config_paths(config, sound_dir="sounds"):
    # Rewrites all sound file paths in config to be relative to sound_dir
    def rewrite_entry(entry):
        if not entry or not isinstance(entry, dict):
            return entry
        files = entry.get("files", [])
        entry["files"] = [os.path.join(sound_dir, os.path.basename(f)) for f in files]
        return entry
    if "global" in config:
        for k, v in config["global"].items():
            config["global"][k] = rewrite_entry(v)
    if "per_app" in config:
        for app, events in config["per_app"].items():
            for k, v in events.items():
                config["per_app"][app][k] = rewrite_entry(v)
    return config


@app.get("/api/soundforge/config")
def soundforge_get_config():
    source_config_path = SOUNDFORGE_CONFIG_PATH if os.path.exists(SOUNDFORGE_CONFIG_PATH) else LEGACY_SOUNDSTAGE_CONFIG_PATH
    if not os.path.exists(source_config_path):
        return jsonify({"ok": True, "config": {"global": {}, "per_app": {}}})
    try:
        with open(source_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Failed to read config: {ex}"}), 500
    if not isinstance(config, dict):
        config = {"global": {}, "per_app": {}}
    return jsonify({"ok": True, "config": config})


@app.post("/api/soundforge/config")
def soundforge_save_config():
    payload = request.get_json(force=True, silent=True) or {}
    config = payload.get("config")
    if not isinstance(config, dict):
        return jsonify({"ok": False, "message": "config object is required"}), 400
    try:
        with open(SOUNDFORGE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        with open(LEGACY_SOUNDSTAGE_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    except Exception as ex:
        return jsonify({"ok": False, "message": f"Failed to save config: {ex}"}), 500
    return jsonify({"ok": True, "message": "SoundForge config saved."})

@app.post("/api/soundforge/export_bundle")
@app.post("/api/soundstage/export_bundle")
def export_soundforge_bundle():
    """Export current config + all referenced sounds as a .B4Gsoundforge zip bundle."""
    try:
        source_config_path = SOUNDFORGE_CONFIG_PATH if os.path.exists(SOUNDFORGE_CONFIG_PATH) else LEGACY_SOUNDSTAGE_CONFIG_PATH
        with open(source_config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except Exception as e:
        return jsonify({"ok": False, "message": f"Failed to load config: {e}"}), 500
    # Gather all sound files
    sound_files = set()
    def gather_files(entry):
        if not entry or not isinstance(entry, dict):
            return
        for f in entry.get("files", []):
            if f: sound_files.add(f)
    if "global" in config:
        for v in config["global"].values():
            gather_files(v)
    if "per_app" in config:
        for events in config["per_app"].values():
            for v in events.values():
                gather_files(v)
    # Prepare bundle
    bundle_path = os.path.join(SOUNDFORGE_SCHEMES_DIR, "exported.B4Gsoundforge")
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Add config (rewrite paths to just 'sounds/filename')
        config_for_bundle = _rewrite_config_paths(json.loads(json.dumps(config)), sound_dir="sounds")
        z.writestr("soundforge_config.json", json.dumps(config_for_bundle, indent=2))
        # Add all sound files
        for f in sound_files:
            if os.path.exists(f):
                z.write(f, arcname=os.path.join("sounds", os.path.basename(f)))
    return send_file(bundle_path, as_attachment=True, download_name="exported.B4Gsoundforge")

@app.post("/api/soundforge/import_bundle")
@app.post("/api/soundstage/import_bundle")
def import_soundforge_bundle():
    """Import a .B4Gsoundforge zip bundle: extract config + sounds, rewrite config paths, activate scheme."""
    if "bundle" not in request.files:
        return jsonify({"ok": False, "message": "No bundle uploaded"}), 400
    bundle = request.files["bundle"]
    scheme_name = request.form.get("scheme_name", "imported_scheme")
    scheme_dir = os.path.join(SOUNDFORGE_SCHEMES_DIR, scheme_name)
    os.makedirs(scheme_dir, exist_ok=True)
    # Extract bundle
    with zipfile.ZipFile(bundle, "r") as z:
        z.extractall(scheme_dir)
    # Move/copy sounds to managed dir
    sounds_src = os.path.join(scheme_dir, "sounds")
    for fname in os.listdir(sounds_src):
        src = os.path.join(sounds_src, fname)
        dst = os.path.join(SOUNDFORGE_SOUNDS_DIR, fname)
        shutil.copy2(src, dst)
    # Load and rewrite config
    config_path = os.path.join(scheme_dir, "soundforge_config.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(scheme_dir, "soundstage_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = _rewrite_config_paths(config, sound_dir="core/soundforge_schemes/sounds")
    # Save as active config
    with open(SOUNDFORGE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    with open(LEGACY_SOUNDSTAGE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return jsonify({"ok": True, "message": f"Imported scheme '{scheme_name}' and activated."})

@app.get("/api/soundforge/list_schemes")
@app.get("/api/soundstage/list_schemes")
def list_soundforge_schemes():
    """List available imported SoundForge schemes."""
    schemes = []
    for name in os.listdir(SOUNDFORGE_SCHEMES_DIR):
        path = os.path.join(SOUNDFORGE_SCHEMES_DIR, name)
        if os.path.isdir(path):
            schemes.append(name)
    if not schemes and os.path.isdir(LEGACY_SOUNDSTAGE_SCHEMES_DIR):
        for name in os.listdir(LEGACY_SOUNDSTAGE_SCHEMES_DIR):
            path = os.path.join(LEGACY_SOUNDSTAGE_SCHEMES_DIR, name)
            if os.path.isdir(path):
                schemes.append(name)
    return jsonify({"ok": True, "schemes": schemes})



###############################
# Collaborative Agent Editing #
###############################

try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    socketio = SocketIO(app, cors_allowed_origins="*")
    # In-memory presence and edit state (not persistent)
    agent_editors = {}  # {agent_name: set(user_ids)}
    agent_locks = {}    # {agent_name: user_id}

    @socketio.on('join_agent')
    def handle_join_agent(data):
        agent = str(data.get('agent', '')).strip().lower()
        user = str(data.get('user', 'anon')).strip()
        join_room(agent)
        agent_editors.setdefault(agent, set()).add(user)
        emit('presence', {'agent': agent, 'editors': list(agent_editors[agent]), 'lock': agent_locks.get(agent)}, room=agent)

    @socketio.on('leave_agent')
    def handle_leave_agent(data):
        agent = str(data.get('agent', '')).strip().lower()
        user = str(data.get('user', 'anon')).strip()
        leave_room(agent)
        if agent in agent_editors:
            agent_editors[agent].discard(user)
            if not agent_editors[agent]:
                agent_editors.pop(agent)
        if agent_locks.get(agent) == user:
            agent_locks.pop(agent)
        emit('presence', {'agent': agent, 'editors': list(agent_editors.get(agent, [])), 'lock': agent_locks.get(agent)}, room=agent)

    @socketio.on('lock_agent')
    def handle_lock_agent(data):
        agent = str(data.get('agent', '')).strip().lower()
        user = str(data.get('user', 'anon')).strip()
        if agent_locks.get(agent) in (None, user):
            agent_locks[agent] = user
        emit('presence', {'agent': agent, 'editors': list(agent_editors.get(agent, [])), 'lock': agent_locks.get(agent)}, room=agent)

    @socketio.on('unlock_agent')
    def handle_unlock_agent(data):
        agent = str(data.get('agent', '')).strip().lower()
        user = str(data.get('user', 'anon')).strip()
        if agent_locks.get(agent) == user:
            agent_locks.pop(agent)
        emit('presence', {'agent': agent, 'editors': list(agent_editors.get(agent, [])), 'lock': agent_locks.get(agent)}, room=agent)

    @socketio.on('edit_agent')
    def handle_edit_agent(data):
        agent = str(data.get('agent', '')).strip().lower()
        user = str(data.get('user', 'anon')).strip()
        content = data.get('content', {})
        # Broadcast edit to all in room except sender
        emit('agent_edit', {'agent': agent, 'user': user, 'content': content}, room=agent, include_self=False)
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


def _default_scheduler_state() -> dict:
    return {"jobs": [], "history": []}


def _default_cicd_state() -> dict:
    return {"last_run": {}, "history": []}


def _default_onboarding_state() -> dict:
    return {
        "steps": {
            "workspace_check": False,
            "security_baseline": False,
            "model_gateway": False,
        },
        "updated_at": "",
    }


@app.route('/api/scheduler', methods=['GET', 'POST'])
def scheduler():
    state = _load_json_state(SCHEDULER_STATE_PATH, _default_scheduler_state())

    if request.method == 'GET':
        return jsonify({"ok": True, **state})

    payload = request.get_json(force=True, silent=True) or {}
    action = str(payload.get("action", "")).strip().lower()

    jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
    history = state.get("history") if isinstance(state.get("history"), list) else []

    if action == "add":
        label = str(payload.get("label", "")).strip() or "unnamed-job"
        command = str(payload.get("command", "")).strip()
        interval_seconds = max(30, int(payload.get("interval_seconds", 300)))
        job_id = f"job-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        jobs.append(
            {
                "id": job_id,
                "label": label,
                "command": command,
                "interval_seconds": interval_seconds,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        state["jobs"] = jobs
        state["history"] = history[-50:]
        _save_json_state(SCHEDULER_STATE_PATH, state)
        return jsonify({"ok": True, "message": "job added", "job_id": job_id, **state})

    if action == "remove":
        job_id = str(payload.get("id", "")).strip()
        if not job_id:
            return jsonify({"ok": False, "message": "id is required"}), 400
        state["jobs"] = [item for item in jobs if str(item.get("id", "")).strip() != job_id]
        _save_json_state(SCHEDULER_STATE_PATH, state)
        return jsonify({"ok": True, "message": "job removed", **state})

    if action == "run_now":
        job_id = str(payload.get("id", "")).strip()
        if not job_id:
            return jsonify({"ok": False, "message": "id is required"}), 400
        job = next((item for item in jobs if str(item.get("id", "")).strip() == job_id), None)
        if not isinstance(job, dict):
            return jsonify({"ok": False, "message": "job not found"}), 404

        command = str(job.get("command", "")).strip()
        if not command:
            result = {"ok": True, "message": "job has no command; treated as metadata-only task", "exit_code": 0}
        else:
            proc = subprocess.run(command, cwd=str(PROJECT_ROOT), shell=True, capture_output=True, text=True)
            result = {
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "")[-2000:],
                "stderr": (proc.stderr or "")[-2000:],
            }

        history.append(
            {
                "job_id": job_id,
                "label": str(job.get("label", "")).strip(),
                "ran_at": datetime.now(timezone.utc).isoformat(),
                **result,
            }
        )
        state["history"] = history[-100:]
        _save_json_state(SCHEDULER_STATE_PATH, state)
        return jsonify({"ok": True, "message": "job executed", "result": result, **state})

    return jsonify({"ok": False, "message": "unsupported scheduler action"}), 400


@app.route('/api/cicd', methods=['GET', 'POST'])
def cicd():
    state = _load_json_state(CICD_STATE_PATH, _default_cicd_state())

    if request.method == 'GET':
        return jsonify({"ok": True, **state})

    payload = request.get_json(force=True, silent=True) or {}
    action = str(payload.get("action", "")).strip().lower()
    suite = str(payload.get("suite", "quick")).strip().lower()

    if action != "run":
        return jsonify({"ok": False, "message": "unsupported cicd action"}), 400

    if suite == "full":
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests"]
    else:
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"]

    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    result = {
        "suite": suite,
        "command": " ".join(cmd),
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-5000:],
        "stderr": (proc.stderr or "")[-5000:],
        "ran_at": datetime.now(timezone.utc).isoformat(),
    }

    history = state.get("history") if isinstance(state.get("history"), list) else []
    history.append(result)
    state["last_run"] = result
    state["history"] = history[-30:]
    _save_json_state(CICD_STATE_PATH, state)
    return jsonify({"ok": True, **state})


@app.route('/api/onboarding', methods=['POST'])
@app.route('/onboarding', methods=['POST'])
def onboarding():
    state = _load_json_state(ONBOARDING_STATE_PATH, _default_onboarding_state())
    payload = request.get_json(force=True, silent=True) or {}
    step = str(payload.get("step", "")).strip().lower()

    if step == "workspace_check":
        checks = {
            "project_root_exists": PROJECT_ROOT.exists(),
            "bus_state_exists": (bus.root / "state").exists(),
            "core_exists": (PROJECT_ROOT / "core").exists(),
            "ui_exists": (PROJECT_ROOT / "ui").exists(),
        }
        state.setdefault("checks", {}).update(checks)
        state.setdefault("steps", {})["workspace_check"] = all(bool(v) for v in checks.values())
    elif step in {"security_baseline", "model_gateway"}:
        state.setdefault("steps", {})[step] = True
    else:
        return jsonify({"ok": False, "message": "unsupported onboarding step"}), 400

    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_json_state(ONBOARDING_STATE_PATH, state)
    return jsonify({"ok": True, **state})


@app.route('/api/onboarding/status', methods=['GET'])
@app.route('/onboarding', methods=['GET'])
def onboarding_status():
    state = _load_json_state(ONBOARDING_STATE_PATH, _default_onboarding_state())
    steps = state.get("steps") if isinstance(state.get("steps"), dict) else {}
    completion = 0.0
    if steps:
        completion = round((sum(1 for value in steps.values() if bool(value)) / max(1, len(steps))) * 100.0, 1)
    return jsonify({"ok": True, "completion_percent": completion, **state})


def main() -> None:
    if socketio is not None:
        socketio.run(app, host="127.0.0.1", port=5005, debug=False)
    else:
        from werkzeug.serving import run_simple
        run_simple("127.0.0.1", 5005, app, use_reloader=False, use_debugger=False, threaded=True)


if __name__ == "__main__":
    main()
