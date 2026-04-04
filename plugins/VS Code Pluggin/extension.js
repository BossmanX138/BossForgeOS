const vscode = require('vscode');

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
