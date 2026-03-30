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
      }
    });

    this.postData();
    this.timer = setInterval(() => this.postData(), 4000);

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
      const payload = {
        events,
        sealQueue: readSealQueue(),
        manualTargets: readManualTargets(),
        delegationStatus: summarizeDelegationStatus(readRecentEvents(80)),
        vscodeContext: this.readVsCodeContext(),
        busRoot: resolveBusRoot(),
        updatedAt: new Date().toISOString()
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

    const encode = (value) => JSON.stringify(value, null, 2)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;');

    return `<!doctype html>
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
    pre {
      margin: 0;
      font-size: 11px;
      max-height: 180px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
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
    <div class="title">Recent Events</div>
    <pre id="events">${encode(initialEvents)}</pre>
  </div>

  <div class="panel">
    <div class="title">VS Code Context</div>
    <pre id="vscode_ctx">${encode(initialContext)}</pre>
  </div>

  <div class="panel">
    <div class="title">Delegated Agents</div>
    <pre id="delegation">${encode(initialDelegation)}</pre>
  </div>

  <script>
    const vscode = acquireVsCodeApi();
    const onlineOnlyKey = 'bosscrafts_manual_online_only';

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
      } catch {
      }
    }

    function render(payload) {
      const seal = payload && payload.sealQueue ? payload.sealQueue : { pending: [], history: [] };
      const events = payload && Array.isArray(payload.events) ? payload.events : [];
      const targets = payload && Array.isArray(payload.manualTargets) ? payload.manualTargets : [];
      const delegation = payload && Array.isArray(payload.delegationStatus) ? payload.delegationStatus : [];
      const vscodeCtx = payload && payload.vscodeContext ? payload.vscodeContext : {};
      document.getElementById('seal').textContent = JSON.stringify(seal, null, 2);
      document.getElementById('events').textContent = JSON.stringify(events, null, 2);
      document.getElementById('delegation').textContent = JSON.stringify(delegation, null, 2);
      document.getElementById('vscode_ctx').textContent = JSON.stringify(vscodeCtx, null, 2);
      document.getElementById('meta').textContent = 'Bus: ' + (payload.busRoot || 'unknown') + ' | Updated: ' + (payload.updatedAt || '');

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
      } else if (msg.type === 'notice') {
        const root = document.getElementById('notice');
        if (root) {
          root.textContent = msg.text || '';
        }
      }
    });

    document.getElementById('refresh').addEventListener('click', () => {
      vscode.postMessage({ type: 'refresh' });
    });

    document.getElementById('manual_send').addEventListener('click', () => {
      const target = (document.getElementById('manual_target').value || '').trim();
      const command = (document.getElementById('manual_command').value || '').trim();
      const args = document.getElementById('manual_args').value || '{}';
      vscode.postMessage({ type: 'manual_command', target, command, args });
    });

    for (const btn of Array.from(document.querySelectorAll('button[data-action]'))) {
      btn.addEventListener('click', () => {
        const action = btn.getAttribute('data-action') || '';
        vscode.postMessage({ type: 'quick_action', action });
      });
    }

    vscode.postMessage({ type: 'ready' });
  </script>
</body>
</html>`;
  }
}

function activate(context) {
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

  const cmdRefreshPanel = vscode.commands.registerCommand('bosscrafts.refreshPanel', async () => {
    sidebarProvider.postData();
  });

  context.subscriptions.push(sidebarReg, cmdStatus, cmdSendSelection, cmdOpenHall, cmdRefreshPanel);
}

function deactivate() {}

module.exports = {
  activate,
  deactivate
};
