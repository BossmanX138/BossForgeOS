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
    const files = fs.readdirSync(dir).filter((name) => name.toLowerCase().endsWith('.json'));
    let hasStale = false;

    for (const name of files) {
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

/**
 * @param {vscode.ExtensionContext} context
 */
function activate(context) {
    // Register onboarding command
    let disposable = vscode.commands.registerCommand('bossforgeos.onboard', () => {
        OnboardingPanel.createOrShow(context.extensionUri);
    });
    context.subscriptions.push(disposable);

    // Register sidebar view provider
    const provider = new OnboardingSidebarProvider(context.extensionUri);
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

    static createOrShow(extensionUri) {
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
        OnboardingPanel.currentPanel = new OnboardingPanel(panel, extensionUri);
    }

    constructor(panel, extensionUri) {
        this.panel = panel;
        this.extensionUri = extensionUri;
        this.panel.webview.html = this.getHtmlForWebview();
        this.panel.onDidDispose(() => {
            OnboardingPanel.currentPanel = undefined;
        });
    }

    getHtmlForWebview() {
        return getOnboardingHtml();
    }
}

// Sidebar webview provider
class OnboardingSidebarProvider {
    constructor(extensionUri) {
        this.extensionUri = extensionUri;
    }
    resolveWebviewView(webviewView) {
        webviewView.webview.options = { enableScripts: true };
        webviewView.webview.html = getOnboardingHtml();
    }
}

// Placeholder onboarding wizard HTML
function getOnboardingHtml() {
    return `
    <html>
    <head>
        <style>
            body { font-family: sans-serif; padding: 1.5em; }
            .step { margin-bottom: 2em; }
            .step input { width: 100%; padding: 0.5em; margin-top: 0.5em; }
            .step label { font-weight: bold; }
            .wizard-title { font-size: 1.5em; margin-bottom: 1em; }
            .wizard-nav { margin-top: 2em; }
            button { padding: 0.5em 1.5em; margin-right: 1em; }
        </style>
    </head>
    <body>
        <div class="wizard-title">BossForgeOS Onboarding Wizard</div>
        <form>
            <div class="step">
                <label for="secret">Secret Key</label>
                <input id="secret" type="password" placeholder="Enter your secret key..." />
            </div>
            <div class="step">
                <label for="token">Access Token</label>
                <input id="token" type="text" placeholder="Enter your access token..." />
            </div>
            <div class="step">
                <label for="voice">Voice Profile</label>
                <input id="voice" type="text" placeholder="Enter your voice profile name..." />
            </div>
            <div class="wizard-nav">
                <button type="submit">Submit</button>
                <button type="button" onclick="alert('Help coming soon!')">Help</button>
            </div>
        </form>
        <div style="margin-top:2em;color:#888;font-size:0.9em;">(This is a placeholder UI. Endpoint integration coming soon.)</div>
    </body>
    </html>
    `;
}

module.exports = {
    activate,
    deactivate
};
