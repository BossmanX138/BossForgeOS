const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, Notification } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const http = require('http');

let mainWindow;
let tray;
let flaskProcess;
let backendManagedByElectron = false;
let trayExitRequested = false;
let trayHintShown = false;

const APP_NAME = process.env.BOSSFORGE_APP_NAME || 'BossForgeOS';
const PROJECT_ROOT = path.resolve(process.env.BOSSFORGE_PROJECT_ROOT || path.join(__dirname, '..', '..'));
const START_SCRIPT_REL = process.env.BOSSFORGE_START_SCRIPT || path.join('launcher', 'bossforge_launcher.py');
const START_SCRIPT_ABS = path.isAbsolute(START_SCRIPT_REL) ? START_SCRIPT_REL : path.join(PROJECT_ROOT, START_SCRIPT_REL);
const HEALTH_PATH = process.env.BOSSFORGE_HEALTH_PATH || '/api/status';
const FLASK_HOST = process.env.BOSSFORGE_HOST || '127.0.0.1';
const FLASK_PORT = Number(process.env.BOSSFORGE_PORT || 5005);
const FLASK_URL = `http://${FLASK_HOST}:${FLASK_PORT}`;

function showTrayMinimizeHint() {
  if (trayHintShown) {
    return;
  }
  trayHintShown = true;

  const hintTitle = `${APP_NAME} minimized to tray`;
  const hintBody = 'Use tray icon right-click > Exit the Forge to fully stop all services.';

  try {
    if (tray && typeof tray.displayBalloon === 'function' && process.platform === 'win32') {
      tray.displayBalloon({
        iconType: 'info',
        title: hintTitle,
        content: hintBody,
      });
      return;
    }
  } catch (err) {
    console.warn('Tray balloon hint failed:', err);
  }

  try {
    if (Notification.isSupported()) {
      new Notification({ title: hintTitle, body: hintBody }).show();
    }
  } catch (err) {
    console.warn('Desktop notification hint failed:', err);
  }
}

function parseStartArgs() {
  const fromJson = process.env.BOSSFORGE_START_ARGS_JSON;
  if (fromJson && fromJson.trim()) {
    try {
      const parsed = JSON.parse(fromJson);
      if (Array.isArray(parsed)) {
        return parsed.map((v) => String(v));
      }
    } catch (err) {
      console.warn('Invalid BOSSFORGE_START_ARGS_JSON, falling back to BOSSFORGE_START_ARGS:', err);
    }
  }

  const raw = process.env.BOSSFORGE_START_ARGS || '';
  const trimmed = raw.trim();
  if (!trimmed) {
    return [];
  }
  return trimmed.split(/\s+/g);
}

function resolvePythonCommand() {
  if (process.env.BOSSFORGE_PYTHON && process.env.BOSSFORGE_PYTHON.trim()) {
    return { command: process.env.BOSSFORGE_PYTHON.trim(), prefixArgs: [] };
  }

  const projectRoot = PROJECT_ROOT;
  const venvPython = path.join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', process.platform === 'win32' ? 'python.exe' : 'python');
  if (fs.existsSync(venvPython)) {
    return { command: venvPython, prefixArgs: [] };
  }

  if (process.platform === 'win32') {
    return { command: 'py', prefixArgs: ['-3'] };
  }

  return { command: 'python3', prefixArgs: [] };
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, 'assets', 'bossforgeos.png'),
    show: false,
  });

  mainWindow.setTitle(`${APP_NAME} Hybrid Shell`);
  mainWindow.loadURL(FLASK_URL);
  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Enforce tray-first lifecycle: close/minimize => hide to tray.
  mainWindow.on('minimize', (event) => {
    event.preventDefault();
    mainWindow.hide();
    showTrayMinimizeHint();
  });

  mainWindow.on('close', (event) => {
    if (!trayExitRequested) {
      event.preventDefault();
      mainWindow.hide();
      showTrayMinimizeHint();
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

function createTray() {
  const iconPath = path.join(__dirname, 'assets', 'bossforgeos.png');
  const trayIcon = nativeImage.createFromPath(iconPath);
  tray = new Tray(trayIcon);
  const contextMenu = Menu.buildFromTemplate([
    { label: `Show ${APP_NAME}`, click: () => mainWindow && mainWindow.show() },
    { type: 'separator' },
    {
      label: 'Exit the Forge',
      click: () => {
        trayExitRequested = true;
        app.quit();
      },
    },
  ]);
  tray.setToolTip(APP_NAME);
  tray.setContextMenu(contextMenu);
  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
    }
  });
}

function startFlask() {
  const { command, prefixArgs } = resolvePythonCommand();
  const isDefaultLauncher = !process.env.BOSSFORGE_START_SCRIPT;
  const includeDefaultHostPortArgs = isDefaultLauncher || process.env.BOSSFORGE_APPEND_DEFAULT_ARGS === '1';
  const launchArgs = [
    ...prefixArgs,
    START_SCRIPT_ABS,
    ...parseStartArgs(),
  ];

  if (includeDefaultHostPortArgs) {
    launchArgs.push('--no-browser', '--host', FLASK_HOST, '--port', String(FLASK_PORT));
  }

  backendManagedByElectron = true;
  flaskProcess = spawn(command, launchArgs, {
    cwd: PROJECT_ROOT,
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
  });

  if (flaskProcess.stdout) {
    flaskProcess.stdout.on('data', (chunk) => {
      process.stdout.write(`[bossforge-backend] ${chunk}`);
    });
  }

  if (flaskProcess.stderr) {
    flaskProcess.stderr.on('data', (chunk) => {
      process.stderr.write(`[bossforge-backend] ${chunk}`);
    });
  }

  flaskProcess.on('error', (err) => {
    console.error('Failed to start backend process:', err);
  });

  flaskProcess.on('close', (code) => {
    console.log(`BossForge backend exited with code ${code}`);
    flaskProcess = null;
    if (!app.isQuitting && backendManagedByElectron) {
      dialog.showErrorBox(
        `${APP_NAME} Backend Stopped`,
        `The Python backend exited unexpectedly (code ${code}). Electron will now close.`
      );
      app.quit();
    }
  });
}

function waitForFlaskReady(retries = 60, delayMs = 1000) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    function probe() {
      http.get(FLASK_URL + HEALTH_PATH, (res) => {
        if (res.statusCode === 200) {
          res.resume();
          resolve();
          return;
        }
        res.resume();
        retry();
      }).on('error', retry);
    }

    function retry() {
      if (++attempts > retries) {
        reject(new Error('BossForge backend did not become ready'));
      } else {
        setTimeout(probe, delayMs);
      }
    }

    probe();
  });
}

async function ensureBackend() {
  try {
    await waitForFlaskReady(2, 400);
    backendManagedByElectron = false;
    return;
  } catch {
    // No live backend detected, start a managed instance.
  }

  startFlask();
  await waitForFlaskReady(90, 1000);
}

app.on('ready', async () => {
  try {
    await ensureBackend();
    createWindow();
    createTray();
  } catch (err) {
    console.error('Hybrid startup failed:', err);
    dialog.showErrorBox(`${APP_NAME} Startup Failed`, String(err && err.message ? err.message : err));
    app.quit();
  }
});

app.on('window-all-closed', () => {
  // No-op: lifecycle is tray-managed. Exit is tray menu only.
});

app.on('before-quit', () => {
  app.isQuitting = true;
  if (flaskProcess) {
    try {
      if (process.platform === 'win32') {
        spawn('taskkill', ['/pid', String(flaskProcess.pid), '/T', '/F'], { windowsHide: true });
      } else {
        flaskProcess.kill('SIGTERM');
      }
    } catch (err) {
      console.error('Failed to terminate backend process tree:', err);
    }
  }
});
