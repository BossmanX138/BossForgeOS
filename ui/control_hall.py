
import atexit
import json
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

from flask import Flask, jsonify, render_template_string, request, send_file


from core.rune.rune_bus import RuneBus, resolve_root_from_env
from core.security.security_sentinel_agent import SecuritySentinelAgent
from modules.os_snapshot import snapshot_all


app = Flask(__name__)
bus = RuneBus(resolve_root_from_env())
PIN_OVERLAY_PROCESS = None
PIN_OVERLAY_VIEW = ""
PIN_OVERLAY_ALPHA = 0.95

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
        :root { --bg:#0f1720; --panel:#182433; --panel2:#213247; --ink:#e8f1ff; --muted:#9db1c9; --line:#35516f; --accent:#f2c96b; --ok:#57d183; --warn:#f2c96b; --bad:#f17171; }
        * { box-sizing:border-box; }
        body { margin:0; font-family:Segoe UI,Tahoma,sans-serif; color:var(--ink); background:radial-gradient(circle at 15% 10%,#1d2a3b,transparent 35%),radial-gradient(circle at 90% 90%,#1b2f2a,transparent 30%),var(--bg); }
        .shell { display:grid; grid-template-columns: 250px 1fr; min-height:100vh; }
        @media (max-width: 980px) { .shell { grid-template-columns: 1fr; } }
        .side { border-right:1px solid var(--line); background:linear-gradient(180deg,#0f1a28,#111f30); padding:14px; }
        .side h1 { margin:0 0 8px; color:var(--accent); font-size:18px; }
        .group-label { margin:10px 0 6px; font-size:11px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }
        .nav-btn { width:100%; text-align:left; margin-bottom:6px; }
        .nav-btn.active { border-color:var(--accent); }
        .wrap { max-width:1200px; margin:0 auto; padding:18px; display:grid; gap:14px; }
        .card { background:linear-gradient(180deg,var(--panel2),var(--panel)); border:1px solid var(--line); border-radius:12px; padding:12px; }
        h1 { margin:0 0 6px; color:var(--accent); font-size:22px; }
        h2 { margin:0 0 10px; color:var(--accent); font-size:16px; }
        .muted { color:var(--muted); font-size:12px; }
        input, select { background:#0e1722; color:var(--ink); border:1px solid var(--line); border-radius:9px; padding:8px; }
        textarea { background:#0e1722; color:var(--ink); border:1px solid var(--line); border-radius:9px; padding:8px; min-height:78px; width:100%; }
        pre { margin:0; max-height:360px; overflow:auto; white-space:pre-wrap; word-break:break-word; background:#0d1621; border:1px solid var(--line); border-radius:10px; padding:10px; font-size:12px; }
        .agent-item { border:1px solid var(--line); border-radius:9px; padding:8px; margin-bottom:6px; background:#132131; }
        .pill { display:inline-block; margin-left:8px; border-radius:999px; padding:1px 8px; border:1px solid var(--line); font-size:11px; }
        .pill.online { color:var(--ok); border-color:var(--ok); }
        .pill.warning, .pill.stale { color:var(--warn); border-color:var(--warn); }
        .pill.offline, .pill.critical { color:var(--bad); border-color:var(--bad); }
        .view-panel { display:none; }
        .view-panel.active { display:block; }
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
    </style>
</head>
<body>
    <div class="shell">
        <aside class="side">
            <h1>BossForgeOS</h1>
            <div class="muted">Control Hall</div>
            <div class="group-label">Operations</div>
            <button class="nav-btn" data-view="view_status" onclick="switchView('view_status')">Agent Status</button>
            <button class="nav-btn" data-view="view_snapshot" onclick="switchView('view_snapshot')">OS Snapshot</button>
            <button class="nav-btn" data-view="view_commands" onclick="switchView('view_commands')">Quick Commands</button>
            <button class="nav-btn" data-view="view_manual" onclick="switchView('view_manual')">Manual Command</button>
            <button class="nav-btn" data-view="view_seal" onclick="switchView('view_seal')">Seal Queue</button>
            <button class="nav-btn" data-view="view_events" onclick="switchView('view_events')">Recent Events</button>
            <button class="nav-btn" data-view="view_cicd" onclick="switchView('view_cicd')" style="color:#57d183; font-weight:bold;">CI/CD</button>
            <button class="nav-btn" data-view="view_onboarding" onclick="switchView('view_onboarding')" style="color:#f2c96b; font-weight:bold;">Onboarding Wizard</button>
            <button class="nav-btn" data-view="view_scheduler" onclick="switchView('view_scheduler')" style="color:#f2c96b; font-weight:bold;">Scheduler</button>
            <button class="nav-btn" data-view="view_cicd" onclick="switchView('view_cicd')" style="color:#57d183; font-weight:bold;">CI/CD</button>
            <div class="group-label">Assistants</div>
            <button class="nav-btn" data-view="view_chat" onclick="switchView('view_chat')">Model Chat</button>
            <button class="nav-btn" data-view="view_maker" onclick="switchView('view_maker')">Agent Maker</button>
            <button class="nav-btn" data-view="view_discovery" onclick="switchView('view_discovery')">Discovery Map</button>
            <button class="nav-btn" data-view="view_security" onclick="switchView('view_security')">Security</button>
            <button class="nav-btn" data-view="view_sounds" onclick="switchView('view_sounds')" style="color:#39ff14; font-weight:bold;">Sounds</button>
            <div class="group-label">Scheduler</div>
            <button class="nav-btn" data-view="view_scheduler" onclick="switchView('view_scheduler')">Scheduler</button>
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
                <div id="toast" class="muted" style="margin-top:8px;"></div>
                <div id="busy_indicator" class="busy-indicator" aria-live="polite">
                    <span class="spinner" aria-hidden="true"></span>
                    <span id="busy_text">Loading...</span>
                </div>
            </section>

            <section id="view_status" class="card view-panel"><h2>Agent Status</h2><div id="agents" class="muted">Loading...</div></section>
            <section id="view_snapshot" class="card view-panel"><h2>OS Snapshot</h2><pre id="snapshot">Loading...</pre></section>

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
            <section id="view_diagnostics" class="card view-panel">
                <h2 style="color:#f17171;">Diagnostics</h2>
                <div class="muted">Agent health, recent errors, and TODOs across the system.</div>
                <pre id="diagnostics_output">Open this panel to load diagnostics.</pre>
                <div class="row"><button onclick="refreshDiagnostics()">Refresh Diagnostics</button></div>
            </section>

            <section id="view_sounds" class="card view-panel">
                <h2 style="color:#39ff14;">Sounds</h2>
                <div class="muted">Sound scheme and soundstage bundle tools.</div>
                <pre id="sound_events">Open this panel to load sound status.</pre>
            </section>

            <section id="view_maker" class="card view-panel">
                <h2>Agent Maker</h2>
                <div class="row"><button onclick="refreshAgentMaker()">Refresh Agents</button></div>
                <pre id="maker_agents">Loading...</pre>
                <div class="row">
                    <input id="maker_name" placeholder="agent name" />
                    <select id="maker_endpoint"></select>
                    <input id="maker_system" value="You are a helpful specialist agent." placeholder="system prompt" />
                    <button onclick="createAgentProfile()">Create/Update</button>
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
                <pre id="maker_result">No agent operation yet.</pre>
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
                <div class="muted">Guide for initial setup: secrets, tokens, and voice profile. (Coming soon)</div>
                <div id="onboarding_status" style="margin-top:12px;"></div>
            </section>

            <section id="view_scheduler" class="card view-panel">
                <h2 style="color:#f2c96b;">Scheduler</h2>
                <div class="muted">Panel for scheduling tasks and rituals. (Coming soon)</div>
                <div id="scheduler_status" style="margin-top:12px;"></div>
            </section>

            <section id="view_cicd" class="card view-panel">
                <h2 style="color:#57d183;">CI/CD</h2>
                <div class="muted">Panel for test/lint results and CI status. (Coming soon)</div>
                <div id="cicd_status" style="margin-top:12px;"></div>
            </section>


                <div class="row">
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="saveSoundScheme()">Save Scheme</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="loadSoundScheme()">Load Scheme</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="createNewScheme()">Create New Scheme</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="exportSoundstageBundle()">Export Bundle</button>
                    <button style="background:#111; color:#39ff14; border-color:#39ff14;" onclick="showImportBundleDialog()">Import Bundle</button>
                </div>
                <input type="file" id="sound_scheme_file" style="display:none;" accept=".json,.soundstage" onchange="handleSchemeFile(event)" />
                <input type="file" id="soundstage_bundle_file" style="display:none;" accept=".B4Gsoundstage,application/zip" onchange="handleImportBundle(event)" />
                <div id="sound_scheme_status" class="muted" style="margin-top:10px;"></div>
                <div id="soundstage_schemes_list" class="muted" style="margin-top:10px;"></div>
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

            el.textContent = lines.join('\n');
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

        async function fetchSoundEvents() {
            const data = await fetchJsonWithTimeout('/api/soundstage/list_schemes');
            if (data && data.ok) {
                soundEvents = [];
                soundScheme = { available_schemes: data.schemes || [] };
                setSoundSchemeStatus('Sound schemes loaded.');
            } else {
                setSoundSchemeStatus('Unable to load sound schemes.');
            }
            renderSoundEvents();
        }

        function switchView(viewId) {
            beginBusy('Loading tab...');
            currentView = viewId;
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
            setTimeout(endBusy, 180);
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
            if (override) {
                const selected = override.value;
                override.innerHTML = '<option value="">(agent default)</option>' + endpoints.map((e) => `<option value="${e}">${e}</option>`).join('');
                if (selected && endpoints.includes(selected)) override.value = selected;
            }
        }

        function renderChat() {
            const root = document.getElementById('chat_log');
            if (!root) return;
            if (!chatHistory.length) {
                root.textContent = 'No messages yet.';
                return;
            }
            root.textContent = chatHistory.map((m) => `${m.role.toUpperCase()} (${m.endpoint}): ${m.content}`).join('\n\n');
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
        }

        async function createAgentProfile() {
            const payload = {
                name: (document.getElementById('maker_name').value || '').trim(),
                endpoint: (document.getElementById('maker_endpoint').value || '').trim(),
                system: (document.getElementById('maker_system').value || '').trim(),
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

        async function refresh() {
            document.getElementById('toast').textContent = 'Refreshing...';

            const statusData = await fetchJsonWithTimeout('/api/status');
            const eventsData = await fetchJsonWithTimeout('/api/events?limit=40');
            const snapData = await fetchJsonWithTimeout('/api/snapshot');
            const sealData = await fetchJsonWithTimeout('/api/archivist/seal');

            if (statusData && statusData.agent_state) {
                renderAgents(statusData.agent_state);
                refreshTargetDropdown(statusData.agent_state);
            } else {
                document.getElementById('agents').innerHTML = '<div class="muted">Status unavailable.</div>';
            }

            document.getElementById('events').textContent = JSON.stringify((eventsData && eventsData.items) ? eventsData.items : eventsData, null, 2);
            document.getElementById('snapshot').textContent = JSON.stringify(snapData, null, 2);
            document.getElementById('seal').textContent = JSON.stringify(sealData, null, 2);

            const failed = [statusData, eventsData, snapData, sealData].filter(x => x && x.ok === false).length;
            document.getElementById('toast').textContent = failed ? ('Loaded with ' + failed + ' endpoint issue(s).') : 'Loaded successfully.';
        }

        // === SoundStage Bundle UI Logic ===
        async function exportSoundstageBundle() {
            const btn = event && event.target;
            if (btn) btn.disabled = true;
            try {
                const res = await fetch('/api/soundstage/export_bundle', { method: 'POST' });
                if (!res.ok) throw new Error('Export failed');
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'exported.B4Gsoundstage';
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
            document.getElementById('soundstage_bundle_file').click();
        }

        async function handleImportBundle(event) {
            const file = event.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('bundle', file);
            formData.append('scheme_name', file.name.replace(/\\.B4Gsoundstage$/i, ''));
            setSoundSchemeStatus('Importing bundle...');
            try {
                const res = await fetch('/api/soundstage/import_bundle', { method: 'POST', body: formData });
                const data = await res.json();
                if (!data.ok) throw new Error(data.message || 'Import failed');
                setSoundSchemeStatus('Imported: ' + data.message);
                await listSoundstageSchemes();
            } catch (e) {
                setSoundSchemeStatus('Import failed: ' + e);
            }
        }

        async function listSoundstageSchemes() {
            try {
                const res = await fetch('/api/soundstage/list_schemes');
                const data = await res.json();
                if (!data.ok) throw new Error('Failed to list schemes');
                const el = document.getElementById('soundstage_schemes_list');
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

        function saveSoundScheme() {
            setSoundSchemeStatus('Save Scheme is not yet wired in this build.');
        }

        function loadSoundScheme() {
            document.getElementById('sound_scheme_file').click();
        }

        function createNewScheme() {
            soundScheme = { name: 'new-scheme', created_at: new Date().toISOString() };
            renderSoundEvents();
            setSoundSchemeStatus('Created in-memory scheme draft.');
        }

        async function handleSchemeFile(event) {
            const file = event.target.files[0];
            if (!file) return;
            try {
                const text = await file.text();
                soundScheme = JSON.parse(text);
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
        refresh();
        listSoundstageSchemes();
        setInterval(refresh, 4000);
        setInterval(refreshPinState, 3000);
    </script>
</body>
</html>
"""


@app.get("/")
def index():
    return render_template_string(PAGE)


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


@app.get("/api/events")
def events():
    limit = int(request.args.get("limit", "50"))
    return jsonify({"items": bus.read_latest_events(limit=limit)})


@app.get("/api/snapshot")
def snapshot():
    return jsonify(snapshot_all())


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
    )
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


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


# === SoundStage Bundle Endpoints ===
import zipfile
import shutil

SOUNDSTAGE_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "core", "soundstage_config.json")
SOUNDSTAGE_SCHEMES_DIR = os.path.join(os.path.dirname(__file__), "..", "core", "soundstage_schemes")
SOUNDSTAGE_SOUNDS_DIR = os.path.join(SOUNDSTAGE_SCHEMES_DIR, "sounds")
os.makedirs(SOUNDSTAGE_SCHEMES_DIR, exist_ok=True)
os.makedirs(SOUNDSTAGE_SOUNDS_DIR, exist_ok=True)

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

@app.post("/api/soundstage/export_bundle")
def export_soundstage_bundle():
    """Export current config + all referenced sounds as a .B4Gsoundstage zip bundle."""
    try:
        with open(SOUNDSTAGE_CONFIG_PATH, "r", encoding="utf-8") as f:
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
    bundle_path = os.path.join(SOUNDSTAGE_SCHEMES_DIR, "exported.B4Gsoundstage")
    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as z:
        # Add config (rewrite paths to just 'sounds/filename')
        config_for_bundle = _rewrite_config_paths(json.loads(json.dumps(config)), sound_dir="sounds")
        z.writestr("soundstage_config.json", json.dumps(config_for_bundle, indent=2))
        # Add all sound files
        for f in sound_files:
            if os.path.exists(f):
                z.write(f, arcname=os.path.join("sounds", os.path.basename(f)))
    return send_file(bundle_path, as_attachment=True, download_name="exported.B4Gsoundstage")

@app.post("/api/soundstage/import_bundle")
def import_soundstage_bundle():
    """Import a .B4Gsoundstage zip bundle: extract config + sounds, rewrite config paths, activate scheme."""
    if "bundle" not in request.files:
        return jsonify({"ok": False, "message": "No bundle uploaded"}), 400
    bundle = request.files["bundle"]
    scheme_name = request.form.get("scheme_name", "imported_scheme")
    scheme_dir = os.path.join(SOUNDSTAGE_SCHEMES_DIR, scheme_name)
    os.makedirs(scheme_dir, exist_ok=True)
    # Extract bundle
    with zipfile.ZipFile(bundle, "r") as z:
        z.extractall(scheme_dir)
    # Move/copy sounds to managed dir
    sounds_src = os.path.join(scheme_dir, "sounds")
    for fname in os.listdir(sounds_src):
        src = os.path.join(sounds_src, fname)
        dst = os.path.join(SOUNDSTAGE_SOUNDS_DIR, fname)
        shutil.copy2(src, dst)
    # Load and rewrite config
    config_path = os.path.join(scheme_dir, "soundstage_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = _rewrite_config_paths(config, sound_dir="core/soundstage_schemes/sounds")
    # Save as active config
    with open(SOUNDSTAGE_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    return jsonify({"ok": True, "message": f"Imported scheme '{scheme_name}' and activated."})

@app.get("/api/soundstage/list_schemes")
def list_soundstage_schemes():
    """List available imported soundstage schemes."""
    schemes = []
    for name in os.listdir(SOUNDSTAGE_SCHEMES_DIR):
        path = os.path.join(SOUNDSTAGE_SCHEMES_DIR, name)
        if os.path.isdir(path):
            schemes.append(name)
    return jsonify({"ok": True, "schemes": schemes})



def main() -> None:
    # Use Flask-SocketIO for collaborative editing
    socketio.run(app, host="0.0.0.0", port=5005, debug=True)


if __name__ == "__main__":
    main()
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

# === Scheduler Endpoint Stub ===
@app.route('/api/scheduler', methods=['GET', 'POST'])
def scheduler():
    # Placeholder for scheduler logic
    if request.method == 'POST':
        # Process scheduling form (future)
        return jsonify({'ok': True, 'message': 'Scheduler step processed.'})
    # For GET, return scheduler status (future)
    return jsonify({'ok': True, 'status': 'Scheduler panel coming soon.'})

# === CI/CD Endpoint Stub ===
@app.route('/api/cicd', methods=['GET', 'POST'])
def cicd():
    # Placeholder for CI/CD logic
    if request.method == 'POST':
        # Process CI/CD form (future)
        return jsonify({'ok': True, 'message': 'CI/CD step processed.'})
    # For GET, return CI/CD status (future)
    return jsonify({'ok': True, 'status': 'CI/CD panel coming soon.'})

# === Onboarding Wizard Endpoint Stub ===
@app.route('/onboarding', methods=['GET', 'POST'])
def onboarding():
    # Placeholder for onboarding wizard logic
    if request.method == 'POST':
        # Process onboarding form (future)
        return jsonify({'ok': True, 'message': 'Onboarding step processed.'})
    # For GET, return onboarding status (future)
    return jsonify({'ok': True, 'status': 'Onboarding wizard coming soon.'})
