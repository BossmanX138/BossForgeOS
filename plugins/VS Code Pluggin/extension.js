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

function stateDir() {
    const dir = path.join(resolveBusRoot(), 'bus', 'state');
    fs.mkdirSync(dir, { recursive: true });
    return dir;
}

function safeReadJson(file) {
    try {
        return JSON.parse(fs.readFileSync(file, 'utf8'));
    } catch {
        return null;
    }
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

function readBusHealth(dir) {
    let files = [];
    try {
        files = fs.readdirSync(dir).filter((name) => name.toLowerCase().endsWith('.json'));
    } catch {
        return 'offline';
    }
    let hasStale = false;

    for (const name of files) {
        // This queue file tracks Archivist seal work, not per-agent heartbeat state.
        if (name === 'archivist_seal_queue.json') {
            continue;
        }
        const payload = safeReadJson(path.join(dir, name));
        const health = healthFromTimestamp(payload && payload.timestamp);
        if (health === 'online') {
            return 'online';
        }
        if (health === 'stale') {
            hasStale = true;
        }
    }

    return hasStale ? 'stale' : 'offline';
}

function applyStatusBarHealth(statusBar, health) {
    if (health === 'online') {
        statusBar.text = 'BossForgeOS: $(check) Online';
        statusBar.tooltip = 'BossForgeOS bus state is active.';
        statusBar.color = undefined;
        return;
    }
    if (health === 'stale') {
        statusBar.text = 'BossForgeOS: $(history) Stale';
        statusBar.tooltip = 'BossForgeOS bus state is stale.';
        statusBar.color = new vscode.ThemeColor('statusBarItem.warningForeground');
        return;
    }
    statusBar.text = 'BossForgeOS: $(circle-slash) Offline';
    statusBar.tooltip = 'BossForgeOS bus state is offline/unavailable.';
    statusBar.color = new vscode.ThemeColor('statusBarItem.errorForeground');
}

function resolveControlHallBaseUrl() {
    const envUrl = process.env.BOSSFORGE_CONTROL_HALL_URL;
    if (envUrl && envUrl.trim()) {
        return envUrl.trim().replace(/\/+$/, '');
    }
    return 'http://127.0.0.1:5005';
}

function escapeHtmlAttr(value) {
    return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/"/g, '&quot;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;');
}

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    const onboardingConfig = {
        controlHallBaseUrl: resolveControlHallBaseUrl()
    };

    // Register onboarding command
    let disposable = vscode.commands.registerCommand('bossforgeos.onboard', () => {
        OnboardingPanel.createOrShow(context.extensionUri, onboardingConfig);
    });
    context.subscriptions.push(disposable);

    // Register sidebar view provider
    const provider = new OnboardingSidebarProvider(context.extensionUri, onboardingConfig);
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider('bossforgeosOnboarding', provider)
    );

    const statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBar.text = 'BossForgeOS: $(sync~spin) Checking...';
    statusBar.tooltip = 'Checking BossForgeOS bus state...';
    statusBar.show();
    context.subscriptions.push(statusBar);

    const busStateDir = stateDir();
    const updateStatus = () => {
        try {
            applyStatusBarHealth(statusBar, readBusHealth(busStateDir));
        } catch {
            applyStatusBarHealth(statusBar, 'offline');
        }
    };

    updateStatus();

    const interval = setInterval(updateStatus, 10000);
    context.subscriptions.push({ dispose: () => clearInterval(interval) });

    const statePattern = new vscode.RelativePattern(busStateDir, '*.json');
    const watcher = vscode.workspace.createFileSystemWatcher(statePattern);
    context.subscriptions.push(
        watcher,
        watcher.onDidCreate(updateStatus),
        watcher.onDidChange(updateStatus),
        watcher.onDidDelete(updateStatus)
    );
}

function deactivate() {}

// Webview panel for onboarding wizard
class OnboardingPanel {
    static currentPanel = undefined;

    static createOrShow(extensionUri, config) {
        const column = vscode.window.activeTextEditor ? vscode.window.activeTextEditor.viewColumn : undefined;
        if (OnboardingPanel.currentPanel) {
            OnboardingPanel.currentPanel.panel.reveal(column);
            return;
        }
        const panel = vscode.window.createWebviewPanel(
            'bossforgeosOnboardingPanel',
            'BossForgeOS Onboarding',
            column || vscode.ViewColumn.One,
            { enableScripts: true }
        );
        OnboardingPanel.currentPanel = new OnboardingPanel(panel, extensionUri, config);
    }

    constructor(panel, extensionUri, config) {
        this.panel = panel;
        this.extensionUri = extensionUri;
        this.config = config;
        this.panel.webview.html = this.getHtmlForWebview();
        this.panel.onDidDispose(() => {
            OnboardingPanel.currentPanel = undefined;
        });
    }

    getHtmlForWebview() {
        return getOnboardingHtml(this.config);
    }
}

// Sidebar webview provider
class OnboardingSidebarProvider {
    constructor(extensionUri, config) {
        this.extensionUri = extensionUri;
        this.config = config;
    }
    resolveWebviewView(webviewView) {
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = getOnboardingHtml(this.config);
    }
}

function getOnboardingHtml(config = {}) {
    const controlHallBaseUrl = escapeHtmlAttr(config.controlHallBaseUrl || resolveControlHallBaseUrl());
    return `
    <html>
    <head>
        <meta charset="UTF-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1.0" />
        <style>
            :root { color-scheme: light dark; }
            body { font-family: var(--vscode-font-family, sans-serif); padding: 1rem; margin: 0; line-height: 1.4; }
            .wizard-title { font-size: 1.25rem; margin-bottom: 0.5rem; font-weight: 600; }
            .wizard-subtitle { color: var(--vscode-descriptionForeground); margin-bottom: 1rem; }
            .step { margin-bottom: 0.85rem; padding: 0.75rem; border: 1px solid var(--vscode-panel-border); border-radius: 8px; }
            .step label { display: block; font-weight: 600; margin-bottom: 0.3rem; }
            .step input, .step select {
                width: 100%;
                box-sizing: border-box;
                padding: 0.45rem;
                border: 1px solid var(--vscode-input-border);
                background: var(--vscode-input-background);
                color: var(--vscode-input-foreground);
                border-radius: 6px;
            }
            .row { display: grid; grid-template-columns: 1fr 1fr; gap: 0.6rem; }
            .wizard-nav { margin-top: 1rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
            button {
                padding: 0.45rem 0.9rem;
                border-radius: 6px;
                border: 1px solid var(--vscode-button-border, transparent);
                cursor: pointer;
            }
            button.primary {
                background: var(--vscode-button-background);
                color: var(--vscode-button-foreground);
            }
            button.secondary {
                background: var(--vscode-button-secondaryBackground);
                color: var(--vscode-button-secondaryForeground);
            }
            .muted { color: var(--vscode-descriptionForeground); font-size: 0.85rem; }
            .status-box {
                margin-top: 1rem;
                border: 1px solid var(--vscode-panel-border);
                border-radius: 8px;
                padding: 0.75rem;
                background: var(--vscode-editorWidget-background);
            }
            .status-line { margin-bottom: 0.4rem; font-size: 0.9rem; }
            .progress {
                width: 100%;
                height: 8px;
                background: var(--vscode-editor-inactiveSelectionBackground);
                border-radius: 999px;
                overflow: hidden;
                margin: 0.35rem 0 0.8rem 0;
            }
            .progress > span {
                display: block;
                height: 100%;
                width: 0%;
                background: var(--vscode-progressBar-background);
                transition: width 140ms ease;
            }
            .pill {
                display: inline-block;
                padding: 0.1rem 0.5rem;
                border-radius: 999px;
                font-size: 0.75rem;
                font-weight: 600;
                margin-left: 0.4rem;
                border: 1px solid var(--vscode-panel-border);
            }
            .pill.ok { color: #2e9d55; }
            .pill.warn { color: #d29922; }
            .pill.err { color: #d73a49; }
            .error { color: #d73a49; font-size: 0.85rem; margin-top: 0.5rem; white-space: pre-wrap; }
            pre { white-space: pre-wrap; font-size: 0.8rem; margin: 0; max-height: 180px; overflow: auto; }
        </style>
    </head>
    <body>
        <div class="wizard-title">BossForgeOS Onboarding Wizard</div>
        <div class="wizard-subtitle">Connects directly to Control Hall onboarding APIs.</div>
        <form id="onboardingForm">
            <div class="step">
                <label for="baseUrl">Control Hall Base URL</label>
                <input id="baseUrl" type="url" value="${controlHallBaseUrl}" placeholder="http://127.0.0.1:5005" />
                <div class="muted">Default: BOSSFORGE_CONTROL_HALL_URL env var or http://127.0.0.1:5005</div>
            </div>
            <div class="step">
                <div class="row">
                    <div>
                        <label for="secret">Secret Key</label>
                        <input id="secret" type="password" placeholder="Enter your secret key..." />
                    </div>
                    <div>
                        <label for="token">Access Token</label>
                        <input id="token" type="text" placeholder="Enter your access token..." />
                    </div>
                </div>
            </div>
            <div class="step">
                <label for="voice">Voice Profile</label>
                <input id="voice" type="text" placeholder="Enter your voice profile name..." />
            </div>
            <div class="wizard-nav">
                <button class="primary" id="submitBtn" type="submit">Run Onboarding</button>
                <button class="secondary" id="refreshBtn" type="button">Refresh Status</button>
            </div>
        </form>
        <div id="error" class="error" aria-live="polite"></div>
        <div class="status-box">
            <div class="status-line">
                API Health:
                <span id="apiStatus" class="pill warn">checking</span>
            </div>
            <div class="status-line">
                Completion:
                <strong id="completionText">0%</strong>
            </div>
            <div class="progress"><span id="completionBar"></span></div>
            <pre id="statusPayload">{}</pre>
        </div>
        <script>
            (function () {
                const vscodeApi = typeof acquireVsCodeApi === 'function' ? acquireVsCodeApi() : null;
                const defaultState = {
                    baseUrl: document.getElementById('baseUrl').value,
                    secret: '',
                    token: '',
                    voice: '',
                    completion: 0,
                    statusPayload: {},
                    apiOk: null,
                    busy: false
                };
                const state = Object.assign({}, defaultState, (vscodeApi && vscodeApi.getState()) || {});

                const form = document.getElementById('onboardingForm');
                const baseUrlInput = document.getElementById('baseUrl');
                const secretInput = document.getElementById('secret');
                const tokenInput = document.getElementById('token');
                const voiceInput = document.getElementById('voice');
                const submitBtn = document.getElementById('submitBtn');
                const refreshBtn = document.getElementById('refreshBtn');
                const errorRoot = document.getElementById('error');
                const statusPayloadRoot = document.getElementById('statusPayload');
                const completionText = document.getElementById('completionText');
                const completionBar = document.getElementById('completionBar');
                const apiStatus = document.getElementById('apiStatus');

                function persistState() {
                    if (vscodeApi) vscodeApi.setState(state);
                }

                function setBusy(isBusy) {
                    state.busy = !!isBusy;
                    submitBtn.disabled = state.busy;
                    refreshBtn.disabled = state.busy;
                    baseUrlInput.disabled = state.busy;
                    submitBtn.textContent = state.busy ? 'Running...' : 'Run Onboarding';
                    persistState();
                }

                function setError(message) {
                    errorRoot.textContent = message || '';
                }

                function setApiStatus(ok) {
                    state.apiOk = ok;
                    apiStatus.className = 'pill ' + (ok === true ? 'ok' : ok === false ? 'err' : 'warn');
                    apiStatus.textContent = ok === true ? 'online' : ok === false ? 'offline' : 'checking';
                    persistState();
                }

                function setCompletion(percent) {
                    const clamped = Math.max(0, Math.min(100, Number(percent || 0)));
                    state.completion = clamped;
                    completionText.textContent = clamped.toFixed(1) + '%';
                    completionBar.style.width = clamped + '%';
                    persistState();
                }

                function setPayload(payload) {
                    state.statusPayload = payload || {};
                    statusPayloadRoot.textContent = JSON.stringify(state.statusPayload, null, 2);
                    persistState();
                }

                function normalizedBaseUrl() {
                    const raw = String(baseUrlInput.value || '').trim().replace(/\\/+$/, '');
                    if (!raw || !/^https?:\\/\\//i.test(raw)) {
                        throw new Error('Control Hall base URL must start with http:// or https://');
                    }
                    return raw;
                }

                async function request(path, options) {
                    const baseUrl = normalizedBaseUrl();
                    state.baseUrl = baseUrl;
                    persistState();
                    const controller = new AbortController();
                    const timeout = setTimeout(() => controller.abort(), 8000);
                    try {
                        const response = await fetch(baseUrl + path, Object.assign({}, options, { signal: controller.signal }));
                        let data = {};
                        try {
                            data = await response.json();
                        } catch {
                            data = {};
                        }
                        if (!response.ok || !data || data.ok === false) {
                            const message = (data && data.message) || ('Request failed with HTTP ' + response.status);
                            throw new Error(message);
                        }
                        return data;
                    } finally {
                        clearTimeout(timeout);
                    }
                }

                async function refreshStatus() {
                    try {
                        setError('');
                        const status = await request('/api/onboarding/status', { method: 'GET' });
                        setApiStatus(true);
                        setPayload(status);
                        setCompletion(status.completion_percent || 0);
                    } catch (error) {
                        setApiStatus(false);
                        setError(String(error && error.message ? error.message : error));
                    }
                }

                function restoreFields() {
                    baseUrlInput.value = state.baseUrl || baseUrlInput.value;
                    secretInput.value = state.secret || '';
                    tokenInput.value = state.token || '';
                    voiceInput.value = state.voice || '';
                    setPayload(state.statusPayload || {});
                    setCompletion(state.completion || 0);
                    setApiStatus(state.apiOk);
                }

                form.addEventListener('submit', async function (event) {
                    event.preventDefault();
                    const secret = String(secretInput.value || '').trim();
                    const token = String(tokenInput.value || '').trim();
                    const voice = String(voiceInput.value || '').trim();
                    if (!secret || !token || !voice) {
                        setError('Secret key, access token, and voice profile are all required.');
                        return;
                    }

                    state.secret = secret;
                    state.token = token;
                    state.voice = voice;
                    persistState();

                    setBusy(true);
                    setError('');
                    try {
                        await request('/api/onboarding', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ step: 'workspace_check' })
                        });
                        await request('/api/onboarding', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ step: 'security_baseline' })
                        });
                        await request('/api/onboarding', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ step: 'model_gateway' })
                        });
                        await refreshStatus();
                    } catch (error) {
                        setApiStatus(false);
                        setError(String(error && error.message ? error.message : error));
                    } finally {
                        setBusy(false);
                    }
                });

                refreshBtn.addEventListener('click', async function () {
                    setBusy(true);
                    await refreshStatus();
                    setBusy(false);
                });

                restoreFields();
                refreshStatus();
            })();
        </script>
    </body>
    </html>
    `;
}

module.exports = {
    activate,
    deactivate
};
