import atexit
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from core.model_gateway_agent import ModelGatewayAgent
from core.rune_bus import RuneBus, resolve_root_from_env
from core.security_sentinel_agent import SecuritySentinelAgent
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
        .row { display:flex; gap:8px; flex-wrap:wrap; align-items:center; }
        button { border:1px solid var(--line); border-radius:9px; background:#172636; color:var(--ink); padding:8px 12px; cursor:pointer; }
        button:hover { border-color:var(--accent); }
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
            <div class="group-label">Assistants</div>
            <button class="nav-btn" data-view="view_chat" onclick="switchView('view_chat')">Model Chat</button>
            <button class="nav-btn" data-view="view_maker" onclick="switchView('view_maker')">Agent Maker</button>
            <button class="nav-btn" data-view="view_security" onclick="switchView('view_security')">Security</button>
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

            <section id="view_chat" class="card view-panel">
                <h2>Model Chat</h2>
                <div class="row"><select id="chat_endpoint"></select><input id="chat_system" value="You are BossForgeOS assistant." placeholder="system prompt" /></div>
                <pre id="chat_log">No messages yet.</pre>
                <textarea id="chat_prompt" placeholder="Message model endpoint..."></textarea>
                <div class="row"><button onclick="sendChat()">Send</button></div>
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
                <pre id="maker_result">No agent operation yet.</pre>
            </section>

            <section id="view_security" class="card view-panel">
                <h2>Security</h2>
                <div class="row"><input id="security_scan_path" placeholder="scan path (blank = workspace)" /><button onclick="runSecurityScan()">Run Scan</button><button onclick="refreshSecurityState()">Refresh State</button></div>
                <pre id="security_findings">Loading...</pre>
                <div class="row"><button onclick="refreshSecretsList()">Refresh Secret Keys</button></div>
                <pre id="security_secrets">No secrets loaded.</pre>
            </section>
        </main>
    </div>

    <script>
        let currentView = 'view_status';
        let chatHistory = [];
        let pinnedOverlayViewId = '';

        function switchView(viewId) {
            currentView = viewId;
            document.querySelectorAll('.view-panel').forEach((el) => el.classList.remove('active'));
            document.querySelectorAll('.nav-btn').forEach((el) => el.classList.remove('active'));
            const panel = document.getElementById(viewId);
            if (panel) panel.classList.add('active');
            const btn = document.querySelector(`.nav-btn[data-view="${viewId}"]`);
            if (btn) btn.classList.add('active');
            syncPinControls();
        }

        async function fetchJsonWithTimeout(url, timeoutMs = 4000) {
            const ctl = new AbortController();
            const timer = setTimeout(() => ctl.abort(), timeoutMs);
            try {
                const res = await fetch(url, { signal: ctl.signal });
                if (!res.ok) return { ok: false, error: 'HTTP ' + res.status };
                return await res.json();
            } catch (err) {
                return { ok: false, error: String(err) };
            } finally {
                clearTimeout(timer);
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

        switchView(currentView);
        refreshPinState();
        refreshChatEndpoints();
        refreshAgentMaker();
        refreshSecurityState();
        refreshSecretsList();
        refresh();
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
    gateway = ModelGatewayAgent(interval_seconds=5)
    return jsonify({"agents": gateway.list_agent_profiles()})


@app.post("/api/model/agents/create")
def model_agents_create():
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    endpoint = str(payload.get("endpoint", "")).strip()
    system = str(payload.get("system", "You are a helpful specialist agent."))
    temperature = float(payload.get("temperature", 0.2))
    max_tokens = int(payload.get("max_tokens", 900))

    gateway = ModelGatewayAgent(interval_seconds=5)
    result = gateway.create_agent_profile(name, endpoint, system, temperature, max_tokens)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/delete")
def model_agents_delete():
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    gateway = ModelGatewayAgent(interval_seconds=5)
    result = gateway.delete_agent_profile(name)
    status = 200 if result.get("ok") else 400
    return jsonify(result), status


@app.post("/api/model/agents/run")
def model_agents_run():
    payload = request.get_json(force=True, silent=True) or {}
    name = str(payload.get("name", "")).strip()
    task = str(payload.get("task", "")).strip()
    endpoint = str(payload.get("endpoint", "")).strip()
    gateway = ModelGatewayAgent(interval_seconds=5)
    result = gateway.run_agent_profile(name, task, endpoint)
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

    gateway = ModelGatewayAgent(interval_seconds=5)
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


def main() -> None:
    app.run(host="127.0.0.1", port=5005, debug=False)


if __name__ == "__main__":
    main()
