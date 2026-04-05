// === REST API Integration Utility ===
const http = require('http');
const https = require('https');

function fetchFromControlHall(path, method = 'GET', data = null, endpoint = 'http://127.0.0.1:5005') {
  return new Promise((resolve, reject) => {
    try {
      const url = new URL(path, endpoint);
      const mod = url.protocol === 'https:' ? https : http;
      const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
      };
      const req = mod.request(url, options, (res) => {
        let body = '';
        res.on('data', (chunk) => (body += chunk));
        res.on('end', () => {
          try {
            resolve(JSON.parse(body));
          } catch {
            resolve({ ok: false, error: 'Invalid JSON', body });
          }
        });
      });
      req.on('error', (err) => reject(err));
      if (data) req.write(JSON.stringify(data));
      req.end();
    } catch (err) {
      reject(err);
    }
  });
}
// Agent Builder backend logic
function agentDir() {
  const root = path.join(__dirname, '../../agents');
  if (!fs.existsSync(root)) fs.mkdirSync(root, { recursive: true });
  return root;
}

function loadAgents() {
  const dir = agentDir();
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));
  const agents = [];
  for (const file of files) {
    try {
      const raw = fs.readFileSync(path.join(dir, file), 'utf8');
      const agent = JSON.parse(raw);
      // Ensure new fields exist for UI compatibility
      if (!Array.isArray(agent.voiceAliases)) agent.voiceAliases = [];
      if (typeof agent.persona !== 'string') agent.persona = '';
      if (typeof agent.voiceProfile !== 'string') agent.voiceProfile = '';
      if (!Array.isArray(agent.rituals)) agent.rituals = [];
      agents.push(agent);
    } catch {}
  }
  return agents;
}

function saveAgent(agent) {
  if (!agent || !agent.name) return false;
  // Ensure new fields exist
  if (!Array.isArray(agent.voiceAliases)) agent.voiceAliases = [];
  if (typeof agent.persona !== 'string') agent.persona = '';
  if (typeof agent.voiceProfile !== 'string') agent.voiceProfile = '';
  if (!Array.isArray(agent.rituals)) agent.rituals = [];
  const file = path.join(agentDir(), `${agent.name.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`);
  fs.writeFileSync(file, JSON.stringify(agent, null, 2), 'utf8');
  return true;
}
const vscode = require('vscode');
const fs = require('fs');
const path = require('path');
const os = require('os');

function resolveBusRoot() {
  const envRoot = process.env.BOSSFORGE_ROOT;
  if (envRoot && envRoot.trim()) {
    return envRoot;
  }
  return path.join(os.homedir(), 'BossCrafts');
}

function commandDir() {
  const root = resolveBusRoot();
  const dir = path.join(root, 'bus', 'commands');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function eventsDir() {
  const root = resolveBusRoot();
  const dir = path.join(root, 'bus', 'events');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function stateDir() {
  const root = resolveBusRoot();
  const dir = path.join(root, 'bus', 'state');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

function writeCommand(target, command, args, issuedBy = 'vscode_extension') {
  const now = new Date();
  const stamp = now.toISOString().replace(/[:.]/g, '-');
  const id = `cmd_${stamp}_${Math.random().toString(16).slice(2, 8)}`;
  const payload = {
    type: 'command',
    target,
    command,
    args: args || {},
    issued_by: issuedBy,
    timestamp: now.toISOString()
  };
  const file = path.join(commandDir(), `${id}.json`);
  fs.writeFileSync(file, JSON.stringify(payload, null, 2), 'utf8');
  return file;
}

function safeReadJson(file) {
  try {
    const raw = fs.readFileSync(file, 'utf8');
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function readRecentEvents(limit = 20) {
  const dir = eventsDir();
  const files = fs
    .readdirSync(dir)
    .map((name) => path.join(dir, name))
    .filter((file) => file.toLowerCase().endsWith('.json'))
    .map((file) => ({
      file,
      mtime: fs.statSync(file).mtimeMs
    }))
    .sort((a, b) => b.mtime - a.mtime)
    .slice(0, limit);

  const items = [];
  for (const entry of files) {
    const payload = safeReadJson(entry.file);
    if (payload && typeof payload === 'object') {
      items.push(payload);
    }
  }
  return items;
}

function readSealQueue() {
  const file = path.join(stateDir(), 'archivist_seal_queue.json');
  const payload = safeReadJson(file);
  if (!payload || typeof payload !== 'object') {
    return { pending: [], history: [] };
  }
  const pending = Array.isArray(payload.pending) ? payload.pending : [];
  const history = Array.isArray(payload.history) ? payload.history : [];
  return { pending, history };
}

function healthFromTimestamp(ts) {
  if (!ts || typeof ts !== 'string') {
    return 'offline';
  }
  const parsed = Date.parse(ts);
  if (!Number.isFinite(parsed)) {
    return 'offline';
  }
  const deltaSec = (Date.now() - parsed) / 1000;
  if (deltaSec <= 60) {
    return 'online';
  }
  if (deltaSec <= 300) {
    return 'stale';
  }
  return 'offline';
}

function readManualTargets() {
  const defaults = ['archivist', 'hearth_tender', 'model_gateway', 'security_sentinel', 'codemage', 'runeforge', 'devlot'];
  const dir = stateDir();
  const files = fs
    .readdirSync(dir)
    .filter((name) => name.toLowerCase().endsWith('.json'));

  const seen = new Set(defaults);
  const alive = [];

  for (const name of files) {
    const target = name.slice(0, -5);
    if (!target || target === 'archivist_seal_queue') {
      continue;
    }

    const payload = safeReadJson(path.join(dir, name));
    const health = payload ? healthFromTimestamp(payload.timestamp) : 'offline';
    if (health === 'online' || health === 'stale') {
      alive.push({ target, health });
      seen.add(target);
    }
  }

  alive.sort((a, b) => {
    if (a.health === b.health) {
      return a.target.localeCompare(b.target);
    }
    return a.health === 'online' ? -1 : 1;
  });

  const fallback = [];
  for (const item of defaults) {
    if (!alive.some((a) => a.target === item)) {
      fallback.push({ target: item, health: 'offline' });
    }
  }

  for (const item of files.map((n) => n.slice(0, -5))) {
    if (!seen.has(item) && item && item !== 'archivist_seal_queue') {
      fallback.push({ target: item, health: 'offline' });
      seen.add(item);
    }
  }

  return [...alive, ...fallback];
}

function summarizeDelegationStatus(events) {
  const tracked = ['codemage', 'runeforge', 'devlot', 'security_sentinel'];
  const items = [];
  const list = Array.isArray(events) ? events : [];

  for (const name of tracked) {
    const hits = list.filter((evt) => evt && evt.source === name);
    const latest = hits.length ? hits[0] : null;
    items.push({
      agent: name,
      events: hits.length,
      last_event: latest && latest.event ? latest.event : 'none',
      last_timestamp: latest && latest.timestamp ? latest.timestamp : 'never'
    });
  }
  return items;
}

function queueQuickCommand(action) {
  if (action === 'daemon_ping') {
    return writeCommand('hearth_tender', 'status_ping', {});
  }
  if (action === 'run_archivist') {
    return writeCommand('archivist', 'on_invoke', {});
  }
  if (action === 'preview_seal') {
    return writeCommand('archivist', 'preview_seal', {});
  }
  if (action === 'approve_latest_seal') {
    const queue = readSealQueue();
    const pending = queue.pending || [];
    if (!pending.length) {
      return null;
    }
    const latest = pending[pending.length - 1];
    const sealId = latest && latest.seal_id ? String(latest.seal_id) : '';
    return writeCommand('archivist', 'approve_seal', sealId ? { seal_id: sealId } : {});
  }
  return null;
}

class BossCraftsSidebarProvider {
  constructor() {
    this.view = null;
    this.timer = null;
    this.ready = false;
  }

  resolveWebviewView(webviewView) {
    this.view = webviewView;
    this.ready = false;
    webviewView.webview.options = { enableScripts: true };
    webviewView.webview.html = this.getHtml();

    webviewView.webview.onDidReceiveMessage(async (message) => {
            if (type === 'run_cli' && message.cmd) {
              const terminal = vscode.window.createTerminal('BossForgeOS CLI');
              terminal.show();
              terminal.sendText(message.cmd);
              return;
            }
      const type = message && message.type ? String(message.type) : '';
      if (type === 'ready') {
        this.ready = true;
        this.postData();
        return;
      }
      if (type === 'refresh') {
        this.postData();
        return;
      }

      if (type === 'quick_action') {
        const action = message && message.action ? String(message.action) : '';
        const file = queueQuickCommand(action);
        if (!file) {
          vscode.window.showWarningMessage('No action executed (possibly no pending seals).');
        } else {
          vscode.window.showInformationMessage(`BossCrafts command queued: ${path.basename(file)}`);
        }
        this.postData();
        return;
      }

      if (type === 'manual_command') {
        const target = message && message.target ? String(message.target).trim() : '';
        const command = message && message.command ? String(message.command).trim() : '';
        const rawArgs = message && message.args ? String(message.args) : '{}';

        if (!target || !command) {
          this.view.webview.postMessage({ type: 'notice', level: 'error', text: 'Target and command are required.' });
          return;
        }

        let parsedArgs = {};
        try {
          const maybe = JSON.parse(rawArgs || '{}');
          parsedArgs = maybe && typeof maybe === 'object' ? maybe : {};
        } catch {
          this.view.webview.postMessage({ type: 'notice', level: 'error', text: 'Args must be valid JSON.' });
          return;
        }

        const file = writeCommand(target, command, parsedArgs, 'vscode_extension_manual');
        vscode.window.showInformationMessage(`BossCrafts command queued: ${path.basename(file)}`);
        this.view.webview.postMessage({ type: 'notice', level: 'info', text: `Queued: ${path.basename(file)}` });
        this.postData();
        return;
      }

      if (type === 'save_agent') {
        const ok = saveAgent(message.agent);
        if (ok) {
          this.view.webview.postMessage({ type: 'agent_notice', text: 'Agent saved.' });
          this.postData();
        } else {
          this.view.webview.postMessage({ type: 'agent_notice', text: 'Failed to save agent.' });
        }
        return;
      }
      if (type === 'delete_agent') {
        const name = message.name;
        if (name) {
          const file = path.join(agentDir(), `${name.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`);
          if (fs.existsSync(file)) fs.unlinkSync(file);
          this.view.webview.postMessage({ type: 'agent_notice', text: 'Agent deleted.' });
          this.postData();
        }
        return;
      }
      if (type === 'test_ritual') {
        // Simulate ritual: echo back the macro/ritual JSON
        const ritual = message.ritual;
        // For now, just echo the ritual as a simulation result
        this.view.webview.postMessage({ type: 'ritual_test_result', result: `Simulated Ritual:\n${JSON.stringify(ritual, null, 2)}` });
        return;
      }
      if (type === 'event_response') {
        // Ritual: respond to an event from the event stream
        const eventIdx = Number(message.eventIdx);
        const response = String(message.response || '').trim();
        // Get the event from the current event list
        const events = readRecentEvents(40);
        const event = events[eventIdx];
        if (!event) {
          this.view.webview.postMessage({ type: 'event_response_status', eventIdx, statusText: 'Event not found.' });
          return;
        }
        // For demonstration, treat response as a command to the event's source or target
        let target = event.target || event.source || 'archivist';
        let command = response;
        let args = {};
        // Optionally, parse response as JSON for command/args
        if (response.startsWith('{')) {
          try {
            const parsed = JSON.parse(response);
            if (parsed.command) {
              command = parsed.command;
              args = parsed.args || {};
            }
          } catch {}
        }
        const file = writeCommand(target, command, args, 'vscode_extension_event_response');
        this.view.webview.postMessage({ type: 'event_response_status', eventIdx, statusText: `Queued: ${path.basename(file)}` });
        vscode.window.showInformationMessage(`BossCrafts event response queued: ${path.basename(file)}`);
        this.postData();
        return;
      }
    });

    this.postData();

    // Enhanced real-time event streaming and notifications
    let lastEventIds = [];
    this.timer = setInterval(() => {
      const events = readRecentEvents(10);
      const newIds = events.map(e => e && e.timestamp ? e.timestamp : e.id || '');
      // Detect new events
      let newCount = 0;
      for (let i = 0; i < newIds.length; ++i) {
        if (!lastEventIds.includes(newIds[i])) newCount++;
        else break;
      }
      if (lastEventIds.length && newCount > 0) {
        if (newCount === 1) {
          const newEvent = events[0];
          if (newEvent && newEvent.event) {
            let level = 'info';
            if (/error|fail|denied|unauthorized/i.test(newEvent.event)) level = 'error';
            else if (/warn|pending|delayed/i.test(newEvent.event)) level = 'warning';
            vscode.window.showInformationMessage(
              `[BossForgeOS] ${newEvent.event}`,
              'View in Event Stream'
            ).then(action => {
              if (action === 'View in Event Stream' && this.view) {
                this.view.show?.(true);
              }
            });
          }
        } else {
          vscode.window.showInformationMessage(
            `[BossForgeOS] ${newCount} new events received`,
            'View in Event Stream'
          ).then(action => {
            if (action === 'View in Event Stream' && this.view) {
              this.view.show?.(true);
            }
          });
        }
      }
      lastEventIds = newIds;
      this.postData();
    }, 2000); // Faster polling for more real-time feel

    webviewView.onDidDispose(() => {
      if (this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
      this.ready = false;
      this.view = null;
    });
  }

  readVsCodeContext() {
    const workspaceFolders = vscode.workspace.workspaceFolders || [];
    const editor = vscode.window.activeTextEditor;
    const ctx = {
      workspaceFolders: workspaceFolders.map((w) => w.uri.fsPath),
      activeFile: '',
      language: '',
      selectionLength: 0,
      selectedTextPreview: ''
    };

    if (!editor) {
      return ctx;
    }

    const selection = editor.selection;
    const selectedText = editor.document.getText(selection || undefined) || '';
    ctx.activeFile = editor.document.uri.fsPath || '';
    ctx.language = editor.document.languageId || '';
    ctx.selectionLength = selectedText.length;
    ctx.selectedTextPreview = selectedText.slice(0, 200);
    return ctx;
  }

  postData() {
    if (!this.view || !this.ready) {
      return;
    }
    try {
      const events = readRecentEvents(40);
      const agents = loadAgents();
      const payload = {
        events,
        sealQueue: readSealQueue(),
        manualTargets: readManualTargets(),
        delegationStatus: summarizeDelegationStatus(readRecentEvents(80)),
        vscodeContext: this.readVsCodeContext(),
        busRoot: resolveBusRoot(),
        updatedAt: new Date().toISOString(),
        agents
      };
      this.view.webview.postMessage({ type: 'data', payload });
    } catch (err) {
      this.view.webview.postMessage({
        type: 'notice',
        level: 'error',
        text: `Sidebar update failed: ${String(err && err.message ? err.message : err)}`
      });
    }
  }

  getHtml() {
    const initialEvents = readRecentEvents(20);
    const initialSeal = readSealQueue();
    const initialDelegation = summarizeDelegationStatus(readRecentEvents(80));
    const initialContext = this.readVsCodeContext();
    const initialBusRoot = resolveBusRoot();
    const initialUpdated = new Date().toISOString();

    // Helper to safely encode HTML
    const encode = (value) => JSON.stringify(value, null, 2)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;');

    // Voice profiles for dropdown
    const voiceProfiles = [
      'Default',
      'Oracle',
      'Herald',
      'Warden',
      'Synth',
      'Custom...'
    ];

    // === Control Hall UI Embed Panel ===
    // VS Code webviews block iframes to localhost by default, so provide both iframe and fallback button
    const controlHallUrl = 'http://127.0.0.1:5005';
    const controlHallPanel = `
      <div class="panel" style="padding:0;overflow:hidden;height:320px;background:#222;">
        <div class="title" style="padding:8px;">Control Hall UI (Preview)</div>
        <iframe id="control_hall_iframe" src="${controlHallUrl}" sandbox="allow-scripts allow-forms allow-same-origin" style="width:100%;height:240px;border:none;background:#222;"></iframe>
        <div style="padding:8px;">
          <button id="open_control_hall_browser">Open Full Control Hall in Browser</button>
          <div class="muted" style="margin-top:4px;">If the embedded UI does not load, use the button above.</div>
        </div>
      </div>
    `;

    return `
    ${controlHallPanel}
  <html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <style>
    body {
      font-family: "Segoe UI", sans-serif;
      margin: 0;
      padding: 10px;
      color: var(--vscode-editor-foreground);
      background: var(--vscode-editor-background);
    }
    .row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
      margin-bottom: 8px;
    }
    button {
      border: 1px solid var(--vscode-button-border, #3f3f3f);
      background: var(--vscode-button-background);
      color: var(--vscode-button-foreground);
      border-radius: 6px;
      padding: 6px 8px;
      cursor: pointer;
      font-size: 12px;
    }
    button:hover {
      background: var(--vscode-button-hoverBackground);
    }
    .panel {
      border: 1px solid var(--vscode-editorWidget-border, #3f3f3f);
      border-radius: 8px;
      padding: 8px;
      margin-bottom: 8px;
    }
    .title {
      margin: 0 0 8px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      opacity: 0.85;
    }
    .event-list {
      max-height: 180px;
      overflow-y: auto;
      margin: 0;
      padding: 0;
      list-style: none;
    }
    .event-item {
      border-bottom: 1px solid var(--vscode-editorWidget-border, #3f3f3f);
      padding: 6px 0;
    }
    .event-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      font-size: 12px;
      cursor: pointer;
    }
    .event-summary {
      font-weight: bold;
      margin-right: 8px;
    }
    .event-details {
      font-size: 11px;
      margin-top: 4px;
      display: none;
    }
    .event-item.expanded .event-details {
      display: block;
    }
    .event-respond {
      margin-top: 6px;
      display: flex;
      gap: 4px;
    }
    .muted {
      opacity: 0.7;
      font-size: 11px;
    }
    label {
      display: block;
      font-size: 11px;
      opacity: 0.85;
      margin-bottom: 4px;
    }
    input, textarea {
      width: 100%;
      box-sizing: border-box;
      border: 1px solid var(--vscode-editorWidget-border, #3f3f3f);
      background: var(--vscode-input-background);
      color: var(--vscode-input-foreground);
      border-radius: 6px;
      padding: 6px 8px;
      font-size: 12px;
      margin-bottom: 6px;
    }
    textarea {
      min-height: 66px;
      resize: vertical;
      font-family: var(--vscode-editor-font-family, Consolas, monospace);
    }
    .notice {
      margin-top: 6px;
      min-height: 16px;
      font-size: 11px;
      opacity: 0.9;
    }
    .busy-indicator {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 8px;
      padding: 4px 10px;
      border: 1px solid var(--vscode-editorWidget-border, #3f3f3f);
      border-radius: 999px;
      background: var(--vscode-editor-background);
      color: var(--vscode-descriptionForeground);
      font-size: 11px;
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
      border-radius: 50%;
      border: 2px solid color-mix(in srgb, var(--vscode-foreground) 20%, transparent);
      border-top-color: var(--vscode-progressBar-background, #f2c96b);
      animation: spin 0.8s linear infinite;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
  </style>
</head>
<body>
  <div class="panel">
    <div class="title">Quick Actions</div>
    <div class="row">
      <button data-action="daemon_ping">Daemon Ping</button>
      <button data-action="run_archivist">Run Archivist</button>
      <button data-action="preview_seal">Refresh Seals</button>
      <button data-action="approve_latest_seal">Approve Latest Seal</button>
    </div>
    <button id="refresh">Refresh Now</button>
    <div id="meta" class="muted" style="margin-top:8px;">Bus: ${initialBusRoot} | Updated: ${initialUpdated}</div>
    <div id="notice" class="notice muted"></div>
    <div id="busy_indicator" class="busy-indicator" aria-live="polite">
      <span class="spinner" aria-hidden="true"></span>
      <span id="busy_text">Loading...</span>
    </div>
  </div>

  <div class="panel">
    <div class="title">Manual Command</div>
    <label style="margin-bottom:8px; display:flex; align-items:center; gap:6px;">
      <input id="manual_online_only" type="checkbox" style="width:auto; margin:0;" />
      Show only online/stale targets
    </label>
    <label for="manual_target">Target</label>
    <select id="manual_target"></select>

    <label for="manual_command">Command</label>
    <input id="manual_command" value="status_ping" placeholder="status_ping" />

    <label for="manual_args">Args JSON</label>
    <textarea id="manual_args">{}</textarea>

    <button id="manual_send">Queue Manual Command</button>
  </div>

  <div class="panel">
    <div class="title">Seal Queue</div>
    <pre id="seal">${encode(initialSeal)}</pre>
  </div>

  <div class="panel">
    <div class="title">Event Stream</div>
    <ul id="event_list" class="event-list"></ul>
  </div>


  <div class="panel">
    <div class="title">Analytics Dashboard</div>
    <canvas id="analytics_chart" width="400" height="180"></canvas>
    <div id="analytics_summary" class="muted"></div>
    <button id="refresh_analytics">Refresh Analytics</button>
  </div>

  <div class="panel">
    <div class="title">VS Code Context</div>
    <pre id="vscode_ctx">${encode(initialContext)}</pre>
  </div>
    // === Analytics Dashboard Logic ===
    function renderAnalytics(events, agents) {
      // Aggregate event counts by agent
      const agentCounts = {};
      (events || []).forEach(evt => {
        const src = evt.source || 'unknown';
        agentCounts[src] = (agentCounts[src] || 0) + 1;
      });
      const labels = Object.keys(agentCounts);
      const data = labels.map(l => agentCounts[l]);
      // Chart.js setup
      if (!window.Chart) {
        const s = document.createElement('script');
        s.src = 'https://cdn.jsdelivr.net/npm/chart.js';
        s.onload = () => renderAnalytics(events, agents);
        document.body.appendChild(s);
        return;
      }
      if (window.analyticsChart) window.analyticsChart.destroy();
      const ctx = document.getElementById('analytics_chart').getContext('2d');
      window.analyticsChart = new Chart(ctx, {
        type: 'bar',
        data: {
          labels,
          datasets: [{
            label: 'Event Count',
            data,
            backgroundColor: 'rgba(54, 162, 235, 0.5)',
            borderColor: 'rgba(54, 162, 235, 1)',
            borderWidth: 1
          }]
        },
        options: {
          responsive: false,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true } }
        }
      });
      // Summary
      const total = data.reduce((a, b) => a + b, 0);
      document.getElementById('analytics_summary').textContent = 'Total events: ' + total + ' | Agents: ' + labels.length;
    }

    document.getElementById('refresh_analytics').addEventListener('click', () => {
      renderAnalytics(window._lastEvents || [], window._lastAgents || []);
    });

    // Hook into data updates
    window._lastEvents = initialEvents;
    window._lastAgents = initialAgents;
    renderAnalytics(initialEvents, initialAgents);

  <div class="panel">
    <div class="title">Delegated Agents</div>
    <pre id="delegation">${encode(initialDelegation)}</pre>
  </div>

  <div class="panel">
    <div class="title">Agent Builder</div>
    <form id="agent_form">
      <label for="agent_name">Name</label>
      <input id="agent_name" type="text" placeholder="Agent name..." required />
      <label for="agent_voice_aliases">Voice Alias(es) <span style="font-size:10px;opacity:0.7;">(comma separated)</span></label>
      <input id="agent_voice_aliases" type="text" placeholder="Alias1, Alias2" />
      <label for="agent_persona">Persona / Archetype</label>
      <input id="agent_persona" type="text" placeholder="e.g. Oracle, Trickster, Guardian" />
      <label for="agent_voice_profile">Voice Profile</label>
      <select id="agent_voice_profile">
        ${voiceProfiles.map(v => `<option value="${v}">${v}</option>`).join('')}
      </select>
      <label for="agent_rituals">Rituals (JSON array of macros)</label>
      <textarea id="agent_rituals" placeholder='[{"name":"Greet","macro":["say Hello!"]}]'></textarea>
      <button id="test_ritual" type="button">Test Ritual</button>
      <label for="agent_type">Type</label>
      <input id="agent_type" type="text" placeholder="Type (e.g., codemage, archivist)" required />
      <label for="agent_desc">Description</label>
      <input id="agent_desc" type="text" placeholder="Short description..." />
      <button type="submit">Save Agent</button>
      <button id="delete_agent" type="button" style="background:#a33;color:#fff;margin-left:8px;">Delete Agent</button>
    </form>
    <div id="ritual_test_result" class="notice"></div>
    <div style="margin:8px 0 4px 0;font-size:12px;opacity:0.8;">Existing Agents:</div>
    <ul id="agent_list" class="event-list"></ul>
    <div id="agent_notice" class="notice"></div>
    <div class="row">
      <button id="import_agent_profile">Import Agent Profile</button>
      <button id="export_agent_profile">Export Agent Profile</button>
      <button id="import_agent_controlhall">Import from Control Hall</button>
      <button id="export_agent_controlhall">Export to Control Hall</button>
      <input id="import_agent_file" type="file" style="display:none;" accept=".json" />
    </div>
    <div class="muted" style="margin-top:8px;">
      <b>Collaborative Editing (Preview):</b> <span id="collab_status">Connecting...</span><br>
      <span id="collab_presence"></span>
    </div>
          // === Collaborative Editing Logic ===
          let socket = null;
          let collabAgent = null;
          let collabUser = 'VSCode-' + Math.random().toString(36).slice(2, 8);
          let collabLock = null;

          function connectCollab(agentName) {
            if (!window.io) {
              document.getElementById('collab_status').textContent = 'Socket.IO not loaded.';
              return;
            }
            if (socket) socket.disconnect();
            socket = io('http://127.0.0.1:5005');
            collabAgent = agentName;
            socket.on('connect', () => {
              document.getElementById('collab_status').textContent = 'Connected.';
              socket.emit('join_agent', { agent: agentName, user: collabUser });
            });
            socket.on('disconnect', () => {
              document.getElementById('collab_status').textContent = 'Disconnected.';
            });
            socket.on('presence', (data) => {
              collabLock = data.lock;
              let editors = (data.editors || []).map(u => u === collabUser ? '<b>me</b>' : u).join(', ');
              document.getElementById('collab_presence').innerHTML = 'Present: ' + editors + (collabLock ? ' <span style="color:#f2c96b">(locked by ' + (collabLock === collabUser ? 'me' : collabLock) + ')</span>' : '');
            });
            socket.on('agent_edit', (data) => {
              if (data.agent === collabAgent && data.user !== collabUser) {
                // Merge remote edit (for demo, just show notice)
                document.getElementById('agent_notice').textContent = 'Remote edit by ' + data.user;
                // TODO: Merge content into form fields (advanced: OT/CRDT)
              }
            });
          }

          function leaveCollab() {
            if (socket && collabAgent) {
              socket.emit('leave_agent', { agent: collabAgent, user: collabUser });
              socket.disconnect();
              socket = null;
            }
          }

          // Load Socket.IO client script
          (function loadSocketIo() {
            if (window.io) return;
            const s = document.createElement('script');
            s.src = 'https://cdn.socket.io/4.7.5/socket.io.min.js';
            s.onload = () => { document.getElementById('collab_status').textContent = 'Socket.IO loaded.'; };
            s.onerror = () => { document.getElementById('collab_status').textContent = 'Socket.IO failed to load.'; };
            document.body.appendChild(s);
          })();

          // Join collab room on agent select
          document.getElementById('agent_name').addEventListener('change', (e) => {
            const name = e.target.value.trim();
            if (name) connectCollab(name);
            else leaveCollab();
          });

          // Broadcast edits (simple: on save)
          document.getElementById('agent_form').addEventListener('submit', (e) => {
            if (socket && collabAgent) {
              const agent = collectAgentForm();
              socket.emit('edit_agent', { agent: collabAgent, user: collabUser, content: agent });
              socket.emit('lock_agent', { agent: collabAgent, user: collabUser });
            }
          });

          // Release lock on delete or leave
          document.getElementById('delete_agent').addEventListener('click', () => {
            if (socket && collabAgent) socket.emit('unlock_agent', { agent: collabAgent, user: collabUser });
          });
          window.addEventListener('beforeunload', leaveCollab);

          function collectAgentForm() {
            // Collect agent form fields into object
            return {
              name: document.getElementById('agent_name').value.trim(),
              voiceAliases: document.getElementById('agent_voice_aliases').value.split(',').map(s => s.trim()).filter(Boolean),
              persona: document.getElementById('agent_persona').value.trim(),
              voiceProfile: document.getElementById('agent_voice_profile').value,
              rituals: (() => { try { return JSON.parse(document.getElementById('agent_rituals').value); } catch { return []; } })(),
              type: document.getElementById('agent_type').value.trim(),
              desc: document.getElementById('agent_desc').value.trim(),
            };
          }
      // === Agent Profile Import/Export Logic ===
      document.getElementById('import_agent_profile').addEventListener('click', () => {
        document.getElementById('import_agent_file').click();
      });
      document.getElementById('import_agent_file').addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (evt) => {
          try {
            const agent = JSON.parse(evt.target.result);
            vscode.postMessage({ type: 'save_agent', agent });
            document.getElementById('agent_notice').textContent = 'Agent profile imported.';
          } catch {
            document.getElementById('agent_notice').textContent = 'Invalid agent profile JSON.';
          }
        };
        reader.readAsText(file);
      });
      document.getElementById('export_agent_profile').addEventListener('click', () => {
        const name = document.getElementById('agent_name').value.trim();
        if (!name) {
          document.getElementById('agent_notice').textContent = 'Enter agent name to export.';
          return;
        }
        // Find agent in list
        const agents = Array.from(document.querySelectorAll('#agent_list .event-item'));
        let agentObj = null;
        for (const item of agents) {
          const summary = item.querySelector('.event-summary');
          if (summary && summary.textContent.startsWith(name + ' ')) {
            const details = item.querySelector('pre');
            if (details) {
              try {
                agentObj = JSON.parse(details.textContent);
              } catch {}
            }
          }
        }
        if (!agentObj) {
          document.getElementById('agent_notice').textContent = 'Agent not found.';
          return;
        }
        const blob = new Blob([JSON.stringify(agentObj, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name + '.json';
        document.body.appendChild(a);
        a.click();
        setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 100);
        document.getElementById('agent_notice').textContent = 'Agent profile exported.';
      });
      // Import agent profile from Control Hall backend
      document.getElementById('import_agent_controlhall').addEventListener('click', async () => {
        const name = document.getElementById('agent_name').value.trim();
        if (!name) {
          document.getElementById('agent_notice').textContent = 'Enter agent name to import.';
          return;
        }
        document.getElementById('agent_notice').textContent = 'Importing from Control Hall...';
        try {
          const res = await fetch('http://127.0.0.1:5005/api/agent/' + encodeURIComponent(name));
          if (!res.ok) throw new Error('HTTP ' + res.status);
          const agent = await res.json();
          vscode.postMessage({ type: 'save_agent', agent });
          document.getElementById('agent_notice').textContent = 'Imported from Control Hall.';
        } catch (e) {
          document.getElementById('agent_notice').textContent = 'Import failed: ' + e;
        }
      });
      // Export agent profile to Control Hall backend
      document.getElementById('export_agent_controlhall').addEventListener('click', async () => {
        const name = document.getElementById('agent_name').value.trim();
        if (!name) {
          document.getElementById('agent_notice').textContent = 'Enter agent name to export.';
          return;
        }
        // Find agent in list
        const agents = Array.from(document.querySelectorAll('#agent_list .event-item'));
        let agentObj = null;
        for (const item of agents) {
          const summary = item.querySelector('.event-summary');
          if (summary && summary.textContent.startsWith(name + ' ')) {
            const details = item.querySelector('pre');
            if (details) {
              try {
                agentObj = JSON.parse(details.textContent);
              } catch {}
            }
          }
        }
        if (!agentObj) {
          document.getElementById('agent_notice').textContent = 'Agent not found.';
          return;
        }
        document.getElementById('agent_notice').textContent = 'Exporting to Control Hall...';
        try {
          const res = await fetch('http://127.0.0.1:5005/api/agent/' + encodeURIComponent(name), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(agentObj)
          });
          if (!res.ok) throw new Error('HTTP ' + res.status);
          document.getElementById('agent_notice').textContent = 'Exported to Control Hall.';
        } catch (e) {
          document.getElementById('agent_notice').textContent = 'Export failed: ' + e;
        }
      });
  </div>



  <div class="panel">
    <div class="title">Onboarding Wizard</div>
    <div id="onboarding_step">
      <div id="onboarding_step_content"></div>
      <div class="row">
        <button id="onboarding_prev">Previous</button>
        <button id="onboarding_next">Next</button>
      </div>
      <div id="onboarding_notice" class="notice"></div>
    </div>
  </div>
  <script>
    // === Enhanced Onboarding Wizard ===
    const onboardingSteps = ['Agent Info', 'Secret/Token', 'Voice Profile', 'Confirm & Save'];
    let onboardingState = { agentName: '', agentType: '', agentPersona: '', secret: '', voiceProfile: 'Default' };
    let onboardingStep = 0;
    function renderOnboardingStep() {
      const step = onboardingSteps[onboardingStep];
      const root = document.getElementById('onboarding_step_content');
      if (!root) return;

      if (step === 'Agent Info') {
        root.innerHTML =
          '<label>Agent Name</label>' +
          '<input id="onboard_agent_name" value="' + (onboardingState.agentName || '') + '" placeholder="e.g. Emberforge" />' +
          '<label>Agent Type</label>' +
          '<input id="onboard_agent_type" value="' + (onboardingState.agentType || '') + '" placeholder="e.g. codemage, archivist" />' +
          '<label>Persona</label>' +
          '<input id="onboard_agent_persona" value="' + (onboardingState.agentPersona || '') + '" placeholder="e.g. Oracle, Guardian" />';
      } else if (step === 'Secret/Token') {
        root.innerHTML =
          '<label>API Secret/Token</label>' +
          '<input id="onboard_secret" value="' + (onboardingState.secret || '') + '" placeholder="sk-..." />' +
          '<div class="muted">Paste your OpenAI, HuggingFace, or other agent secret/token.</div>';
      } else if (step === 'Voice Profile') {
        root.innerHTML =
          '<label>Voice Profile</label>' +
          '<select id="onboard_voice_profile">' +
            '<option value="Default">Default</option>' +
            '<option value="Oracle">Oracle</option>' +
            '<option value="Herald">Herald</option>' +
            '<option value="Warden">Warden</option>' +
            '<option value="Synth">Synth</option>' +
            '<option value="Custom...">Custom...</option>' +
          '</select>';
      } else {
        root.innerHTML =
          '<b>Review and Confirm:</b>' +
          '<ul>' +
            '<li><b>Name:</b> ' + onboardingState.agentName + '</li>' +
            '<li><b>Type:</b> ' + onboardingState.agentType + '</li>' +
            '<li><b>Persona:</b> ' + onboardingState.agentPersona + '</li>' +
            '<li><b>Secret:</b> ' + (onboardingState.secret ? '********' : '(none)') + '</li>' +
            '<li><b>Voice Profile:</b> ' + onboardingState.voiceProfile + '</li>' +
          '</ul>' +
          '<button id="onboard_save_btn">Save Agent & Secret</button>';
      }

      document.getElementById('onboarding_notice').textContent = '';
      if (step === 'Voice Profile' && onboardingState.voiceProfile) {
        document.getElementById('onboard_voice_profile').value = onboardingState.voiceProfile;
      }
      if (step === 'Confirm & Save') {
        document.getElementById('onboard_save_btn').onclick = function() {
          // Save agent and secret (simulate)
          document.getElementById('onboarding_notice').textContent = 'Agent and secret saved!';
        };
      }
    }

    function validateOnboardingStep(step) {
      if (step === 'Agent Info') {
        if (!onboardingState.agentName) return 'Agent name required.';
        if (!onboardingState.agentType) return 'Agent type required.';
      }
      if (step === 'Secret/Token') {
        if (!onboardingState.secret) return 'Secret/token required.';
        if (onboardingState.secret.length < 8) return 'Secret/token too short.';
      }
      return '';
    }

    function saveOnboardingStep(step) {
      if (step === 'Agent Info') {
        onboardingState.agentName = (document.getElementById('onboard_agent_name')?.value || '').trim();
        onboardingState.agentType = (document.getElementById('onboard_agent_type')?.value || '').trim();
        onboardingState.agentPersona = (document.getElementById('onboard_agent_persona')?.value || '').trim();
      } else if (step === 'Secret/Token') {
        onboardingState.secret = (document.getElementById('onboard_secret')?.value || '').trim();
      } else if (step === 'Voice Profile') {
        onboardingState.voiceProfile = document.getElementById('onboard_voice_profile')?.value || onboardingState.voiceProfile;
      }
    }

    function onboardingNav(dir) {
      const step = onboardingSteps[onboardingStep];
      saveOnboardingStep(step);
      if (dir > 0) {
        const err = validateOnboardingStep(step);
        if (err) {
          document.getElementById('onboarding_notice').textContent = err;
          return;
        }
      }
      onboardingStep += dir;
      if (onboardingStep < 0) onboardingStep = 0;
      if (onboardingStep >= onboardingSteps.length) onboardingStep = onboardingSteps.length - 1;
      renderOnboardingStep();
    }
    document.getElementById('onboarding_prev').onclick = () => onboardingNav(-1);
    document.getElementById('onboarding_next').onclick = () => onboardingNav(1);
    renderOnboardingStep();
  </script>

  <div class="panel">
    <div class="title">BossForgeOS CLI</div>
    <input id="cli_input" type="text" placeholder="bforge status" style="width:70%;margin-right:8px;" />
    <button id="run_cli_btn">Run CLI Command</button>
    <div id="cli_notice" class="notice">Run any BossForgeOS CLI command directly in the VS Code terminal.</div>
  </div>

  <div class="panel">
    <div class="title">Scheduler (Control Hall)</div>
    <div id="scheduler_status">Loading...</div>
    <button id="refresh_scheduler">Refresh Scheduler Status</button>
  </div>

  <div class="panel">
    <div class="title">CI/CD (Control Hall)</div>
    <div id="cicd_status">Loading...</div>
    <button id="refresh_cicd">Refresh CI/CD Status</button>
  </div>
    // === REST API Panel Fetch Logic ===
    async function fetchPanelStatus(panel, url, statusId) {
      const statusEl = document.getElementById(statusId);
      if (!statusEl) {
        return;
      }
      statusEl.textContent = 'Loading...';
      try {
        const res = await fetch(url);
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        statusEl.textContent = JSON.stringify(data, null, 2);
      } catch (e) {
        statusEl.textContent = 'Error: ' + e;
      }
    }
    const refreshOnboardingBtn = document.getElementById('refresh_onboarding');
    if (refreshOnboardingBtn) {
      refreshOnboardingBtn.addEventListener('click', () => fetchPanelStatus('onboarding', 'http://127.0.0.1:5005/onboarding', 'onboarding_status'));
    }

    const refreshSchedulerBtn = document.getElementById('refresh_scheduler');
    if (refreshSchedulerBtn) {
      refreshSchedulerBtn.addEventListener('click', () => fetchPanelStatus('scheduler', 'http://127.0.0.1:5005/api/scheduler', 'scheduler_status'));
    }

    const refreshCicdBtn = document.getElementById('refresh_cicd');
    if (refreshCicdBtn) {
      refreshCicdBtn.addEventListener('click', () => fetchPanelStatus('cicd', 'http://127.0.0.1:5005/api/cicd', 'cicd_status'));
    }
    // Initial load
    if (document.getElementById('onboarding_status')) {
      fetchPanelStatus('onboarding', 'http://127.0.0.1:5005/onboarding', 'onboarding_status');
    }
    if (document.getElementById('scheduler_status')) {
      fetchPanelStatus('scheduler', 'http://127.0.0.1:5005/api/scheduler', 'scheduler_status');
    }
    if (document.getElementById('cicd_status')) {
      fetchPanelStatus('cicd', 'http://127.0.0.1:5005/api/cicd', 'cicd_status');
    }

  <script>
    // Open Control Hall in browser if button is clicked
    document.addEventListener('DOMContentLoaded', function() {
      const btn = document.getElementById('open_control_hall_browser');
      if (btn) {
        btn.addEventListener('click', function() {
          window.open('${controlHallUrl}', '_blank');
        });
      }
    });
    const vscode = acquireVsCodeApi();
    const onlineOnlyKey = 'bosscrafts_manual_online_only';
    let pendingLoads = 0;

    function beginBusy(message, autoStopMs = 3500) {
      pendingLoads += 1;
      const root = document.getElementById('busy_indicator');
      const text = document.getElementById('busy_text');
      if (root && text) {
        if (message) text.textContent = message;
        root.classList.add('active');
      }
      if (autoStopMs > 0) {
        setTimeout(() => endBusy(), autoStopMs);
      }
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

    function getOnlineOnlyPreference() {
      try {
        return localStorage.getItem(onlineOnlyKey) === '1';
      } catch {
        return false;
      }
    }

    function setOnlineOnlyPreference(value) {
      try {
        localStorage.setItem(onlineOnlyKey, value ? '1' : '0');
      } catch {}
    }

    function renderEventList(events) {
      const root = document.getElementById('event_list');
      root.innerHTML = '';
      if (!Array.isArray(events) || !events.length) {
        root.innerHTML = '<li class="muted">No recent events.</li>';
        return;
      }
      events.forEach((evt, idx) => {
        const li = document.createElement('li');
        li.className = 'event-item';
        li.innerHTML =
          '<div class="event-header">' +
            '<span class="event-summary">' + (evt.event || evt.type || 'event') + '</span>' +
            '<span class="muted">' + (evt.timestamp ? evt.timestamp.slice(0, 19).replace('T', ' ') : '') + '</span>' +
            '<button class="expand-btn" data-idx="' + idx + '">Details</button>' +
          '</div>' +
          '<div class="event-details">' +
            '<pre>' + encode(evt) + '</pre>' +
            '<div class="event-respond">' +
              '<input type="text" class="response-input" placeholder="Ritual command or response..." />' +
              '<button class="respond-btn" data-idx="' + idx + '">Respond</button>' +
            '</div>' +
            '<div class="response-status muted"></div>' +
          '</div>';
        root.appendChild(li);
      });

      // Expand/collapse logic
      root.querySelectorAll('.expand-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          const idx = btn.getAttribute('data-idx');
          const item = root.children[idx];
          item.classList.toggle('expanded');
        });
      });

      // Respond logic
      root.querySelectorAll('.respond-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          const idx = btn.getAttribute('data-idx');
          const item = root.children[idx];
          const input = item.querySelector('.response-input');
          const status = item.querySelector('.response-status');
          const value = input.value.trim();
          if (!value) {
            status.textContent = 'Enter a response.';
            return;
          }
          status.textContent = 'Sending...';
          beginBusy('Sending event response...');
          vscode.postMessage({ type: 'event_response', eventIdx: idx, response: value });
        });
      });
    }

    function render(payload) {
      function renderAgentList(agents) {
        const root = document.getElementById('agent_list');
        root.innerHTML = '';
        if (!Array.isArray(agents) || !agents.length) {
          root.innerHTML = '<li class="muted">No agents defined.</li>';
          return;
        }
        agents.forEach((agent, idx) => {
          const li = document.createElement('li');
          li.className = 'event-item';
          let details = '';
          if (agent.locked || agent.license_required) {
            details = encode(agent.model_card || { message: 'Model card unavailable.' });
          } else {
            details = encode(agent);
          }
          li.innerHTML =
            '<div class="event-header">' +
              '<span class="event-summary">' + (agent.name || 'unnamed') + ' (' + (agent.type || 'type') + ')</span>' +
              '<button class="expand-agent-btn" data-idx="' + idx + '">Details</button>' +
            '</div>' +
            '<div class="event-details">' +
              '<pre>' + details + '</pre>' +
              '<button class="edit-agent-btn" data-idx="' + idx + '">Edit</button>' +
            '</div>';
          root.appendChild(li);
        });
        // Expand/collapse logic
        root.querySelectorAll('.expand-agent-btn').forEach(btn => {
          btn.addEventListener('click', e => {
            const idx = btn.getAttribute('data-idx');
            const item = root.children[idx];
            item.classList.toggle('expanded');
          });
        });
        // Edit logic
        root.querySelectorAll('.edit-agent-btn').forEach(btn => {
          btn.addEventListener('click', e => {
            const idx = btn.getAttribute('data-idx');
            const agent = agents[idx];
            document.getElementById('agent_name').value = agent.name || '';
            document.getElementById('agent_voice_aliases').value = (agent.voiceAliases || []).join(', ');
            document.getElementById('agent_persona').value = agent.persona || '';
            document.getElementById('agent_voice_profile').value = agent.voiceProfile || 'Default';
            document.getElementById('agent_rituals').value = JSON.stringify(agent.rituals || [], null, 2);
            document.getElementById('agent_type').value = agent.type || '';
            document.getElementById('agent_desc').value = agent.description || '';
          });
        });
      }
      const seal = payload && payload.sealQueue ? payload.sealQueue : { pending: [], history: [] };
      const events = payload && Array.isArray(payload.events) ? payload.events : [];
      const targets = payload && Array.isArray(payload.manualTargets) ? payload.manualTargets : [];
      const delegation = payload && Array.isArray(payload.delegationStatus) ? payload.delegationStatus : [];
      const vscodeCtx = payload && payload.vscodeContext ? payload.vscodeContext : {};
      document.getElementById('seal').textContent = JSON.stringify(seal, null, 2);
      renderEventList(events);
      document.getElementById('delegation').textContent = JSON.stringify(delegation, null, 2);
      document.getElementById('vscode_ctx').textContent = JSON.stringify(vscodeCtx, null, 2);
      document.getElementById('meta').textContent = 'Bus: ' + (payload.busRoot || 'unknown') + ' | Updated: ' + (payload.updatedAt || '');
      renderAgentList(payload.agents || []);

      const targetSelect = document.getElementById('manual_target');
      const onlineOnlyInput = document.getElementById('manual_online_only');
      if (targetSelect) {
        if (onlineOnlyInput && !onlineOnlyInput.dataset.bound) {
          onlineOnlyInput.checked = getOnlineOnlyPreference();
          onlineOnlyInput.addEventListener('change', () => {
            setOnlineOnlyPreference(!!onlineOnlyInput.checked);
            render(payload);
          });
          onlineOnlyInput.dataset.bound = '1';
        }

        const onlineOnly = onlineOnlyInput ? !!onlineOnlyInput.checked : false;
        const visibleTargets = onlineOnly
          ? targets.filter((item) => (item.health || '') === 'online' || (item.health || '') === 'stale')
          : targets;

        const previous = targetSelect.value || 'archivist';
        targetSelect.innerHTML = '';
        for (const item of visibleTargets) {
          const option = document.createElement('option');
          option.value = item.target || '';
          option.textContent = (item.target || '') + ' (' + (item.health || 'offline') + ')';
          targetSelect.appendChild(option);
        }
        if (visibleTargets.length === 0) {
          const option = document.createElement('option');
          option.value = 'archivist';
          option.textContent = onlineOnly ? 'No online targets' : 'archivist (offline)';
          targetSelect.appendChild(option);
        }
        const stillExists = Array.from(targetSelect.options).some((opt) => opt.value === previous);
        targetSelect.value = stillExists ? previous : targetSelect.options[0].value;
      }
    }

    window.addEventListener('message', (event) => {
      const msg = event.data || {};
      if (msg.type === 'data') {
        render(msg.payload || {});
        endBusy();
      } else if (msg.type === 'notice') {
        const root = document.getElementById('notice');
        if (root) {
          root.textContent = msg.text || '';
        }
        endBusy();
      } else if (msg.type === 'event_response_status') {
        // Show response status for the event
        const { eventIdx, statusText } = msg;
        const root = document.getElementById('event_list');
        if (root && root.children[eventIdx]) {
          const status = root.children[eventIdx].querySelector('.response-status');
          if (status) status.textContent = statusText;
        }
        endBusy();
      } else if (msg.type === 'agent_notice') {
        const root = document.getElementById('agent_notice');
        if (root) root.textContent = msg.text || '';
        endBusy();
      } else if (msg.type === 'ritual_test_result') {
        const root = document.getElementById('ritual_test_result');
        if (root) root.textContent = msg.result || '';
        endBusy();
      }
    });

    document.getElementById('agent_form').addEventListener('submit', (e) => {
      e.preventDefault();
      const name = document.getElementById('agent_name').value.trim();
      const voiceAliases = document.getElementById('agent_voice_aliases').value.split(',').map(s => s.trim()).filter(Boolean);
      const persona = document.getElementById('agent_persona').value.trim();
      const voiceProfile = document.getElementById('agent_voice_profile').value;
      let rituals = [];
      try {
        rituals = JSON.parse(document.getElementById('agent_rituals').value || '[]');
        if (!Array.isArray(rituals)) throw new Error('Rituals must be an array.');
      } catch {
        document.getElementById('agent_notice').textContent = 'Rituals must be valid JSON array.';
        return;
      }
      const type = document.getElementById('agent_type').value.trim();
      const description = document.getElementById('agent_desc').value.trim();
      beginBusy('Saving agent...');
      vscode.postMessage({ type: 'save_agent', agent: { name, voiceAliases, persona, voiceProfile, rituals, type, description } });
    });

    document.getElementById('delete_agent').addEventListener('click', (e) => {
      e.preventDefault();
      const name = document.getElementById('agent_name').value.trim();
      if (name && confirm('Delete agent ' + name + '?')) {
        beginBusy('Deleting agent...');
        vscode.postMessage({ type: 'delete_agent', name });
      }
    });

    document.getElementById('test_ritual').addEventListener('click', (e) => {
      e.preventDefault();
      let rituals = [];
      try {
        rituals = JSON.parse(document.getElementById('agent_rituals').value || '[]');
        if (!Array.isArray(rituals) || !rituals.length) throw new Error('No rituals defined.');
      } catch {
        document.getElementById('ritual_test_result').textContent = 'Rituals must be valid JSON array.';
        return;
      }
      // For now, test the first ritual
      beginBusy('Testing ritual...');
      vscode.postMessage({ type: 'test_ritual', ritual: rituals[0] });
    });

    document.getElementById('refresh').addEventListener('click', () => {
      beginBusy('Refreshing panel...');
      vscode.postMessage({ type: 'refresh' });
    });

    // CLI command logic
    document.getElementById('run_cli_btn').addEventListener('click', () => {
      const cmd = document.getElementById('cli_input').value.trim();
      if (!cmd) {
        document.getElementById('cli_notice').textContent = 'Enter a CLI command.';
        return;
      }
      beginBusy('Running CLI command...', 1200);
      vscode.postMessage({ type: 'run_cli', cmd });
      document.getElementById('cli_notice').textContent = 'Sent to terminal: ' + cmd;
    });

    document.getElementById('manual_send').addEventListener('click', () => {
      const target = (document.getElementById('manual_target').value || '').trim();
      const command = (document.getElementById('manual_command').value || '').trim();
      const args = document.getElementById('manual_args').value || '{}';
      beginBusy('Queueing manual command...');
      vscode.postMessage({ type: 'manual_command', target, command, args });
    });

    for (const btn of Array.from(document.querySelectorAll('button[data-action]'))) {
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-action') || '';
        beginBusy('Queueing action...');
        vscode.postMessage({ type: 'quick_action', action });
      });
    }

    beginBusy('Loading panel...');
    vscode.postMessage({ type: 'ready' });
  </script>
</body>
</html>`;
  }
}

function activate(context) {
    // (No-op: CLI command is now handled in the main webview message handler above)
  // Register BossForgeOS CLI command
  const cmdRunCLI = vscode.commands.registerCommand('bosscrafts.runCLI', async () => {
    const cliCmd = await vscode.window.showInputBox({
      prompt: 'Enter BossForgeOS CLI command (e.g., bforge status)',
      placeHolder: 'bforge status'
    });
    if (!cliCmd) return;
    const terminal = vscode.window.createTerminal('BossForgeOS CLI');
    terminal.show();
    terminal.sendText(cliCmd);
  });
  // Status bar item for BossForgeOS health
  const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.text = 'BossForgeOS: $(sync~spin) Checking...';
  statusBar.show();
  async function updateStatusBar() {
    const endpoint = vscode.workspace.getConfiguration().get('bosscrafts.endpoint', 'http://127.0.0.1:5005');
    try {
      const res = await fetch(`${endpoint}/health`);
      if (res.ok) {
        statusBar.text = 'BossForgeOS: $(check) Online';
        statusBar.tooltip = 'BossForgeOS Control Hall is online.';
      } else {
        statusBar.text = 'BossForgeOS: $(alert) Unreachable';
        statusBar.tooltip = 'BossForgeOS Control Hall is not responding.';
      }
    } catch {
      statusBar.text = 'BossForgeOS: $(alert) Unreachable';
      statusBar.tooltip = 'BossForgeOS Control Hall is not responding.';
    }
  }
  updateStatusBar();
  setInterval(updateStatusBar, 10000);

  const sidebarProvider = new BossCraftsSidebarProvider();
  const sidebarReg = vscode.window.registerWebviewViewProvider('bosscrafts.controlPanel', sidebarProvider);

  const cmdStatus = vscode.commands.registerCommand('bosscrafts.status', async () => {
    const root = resolveBusRoot();
    await vscode.window.showInformationMessage(`BossCrafts bus root: ${root}`);
  });

  const cmdSendSelection = vscode.commands.registerCommand('bosscrafts.sendSelectionToCodeMage', async () => {
    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showWarningMessage('No active editor.');
      return;
    }

    const selection = editor.document.getText(editor.selection);
    const content = selection && selection.trim() ? selection : editor.document.getText();
    const docPath = editor.document.uri.fsPath;

    const file = writeCommand('codemage', 'analyze_selection', {
      file_path: docPath,
      content,
      language: editor.document.languageId
    });

    vscode.window.showInformationMessage(`BossCrafts command queued: ${path.basename(file)}`);
  });

  const cmdOpenHall = vscode.commands.registerCommand('bosscrafts.openControlHall', async () => {
    const uri = vscode.Uri.parse('http://127.0.0.1:5005');
    await vscode.env.openExternal(uri);
  });

  // Legacy compatibility: keep older onboarding command wired to the unified panel.
  const cmdLegacyOnboard = vscode.commands.registerCommand('bossforgeos.onboard', async () => {
    await vscode.commands.executeCommand('workbench.view.extension.bosscraftsSidebar');
    await vscode.commands.executeCommand('bosscrafts.controlPanel.focus');
    sidebarProvider.postData();
  });

  const cmdRefreshPanel = vscode.commands.registerCommand('bosscrafts.refreshPanel', async () => {
    sidebarProvider.postData();
  });

  context.subscriptions.push(sidebarReg, cmdStatus, cmdSendSelection, cmdOpenHall, cmdLegacyOnboard, cmdRefreshPanel, cmdRunCLI);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate
};
