'use strict';

const { app, BrowserWindow, shell, Menu, Tray, nativeImage } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const net = require('net');
const http = require('http');

// ── Configuration ─────────────────────────────────────────────────────────────

const PREFERRED_PORT = 8000;
const HEALTH_TIMEOUT_MS = 60_000;
const HEALTH_POLL_MS    = 500;

// ── State ─────────────────────────────────────────────────────────────────────

let mainWindow  = null;
let backendProcess = null;
let backendPort = PREFERRED_PORT;
let tray        = null;
let isQuitting  = false;   // set to true only when user explicitly chooses Quit

// Brand icon — used for window, taskbar and tray
const iconPath = path.join(__dirname, 'build', 'icon.png');
const appIcon  = nativeImage.createFromPath(iconPath);

// ── Helpers ───────────────────────────────────────────────────────────────────

function findFreePort(preferred) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(preferred, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', () => {
      const s2 = net.createServer();
      s2.listen(0, '127.0.0.1', () => {
        const { port } = s2.address();
        s2.close(() => resolve(port));
      });
    });
  });
}

function waitForBackend(port) {
  return new Promise((resolve, reject) => {
    const deadline = Date.now() + HEALTH_TIMEOUT_MS;
    const check = () => {
      if (Date.now() > deadline) {
        return reject(new Error(`Backend did not start within ${HEALTH_TIMEOUT_MS / 1000}s`));
      }
      const req = http.get(`http://127.0.0.1:${port}/health`, (res) => {
        if (res.statusCode === 200) resolve();
        else setTimeout(check, HEALTH_POLL_MS);
      });
      req.on('error', () => setTimeout(check, HEALTH_POLL_MS));
      req.setTimeout(1000, () => { req.destroy(); setTimeout(check, HEALTH_POLL_MS); });
    };
    check();
  });
}

function getBackendExe() {
  if (app.isPackaged) {
    const exe = process.platform === 'win32' ? 'VajraStocks.exe' : 'VajraStocks';
    return path.join(process.resourcesPath, 'backend', exe);
  }
  return null; // dev mode — backend assumed already running
}

// ── Backend lifecycle ─────────────────────────────────────────────────────────

function startBackend(port) {
  const exe = getBackendExe();
  if (!exe) return;

  backendProcess = spawn(exe, [], {
    env: {
      ...process.env,
      VAJRA_PORT: String(port),
      VAJRA_ELECTRON: '1',
    },
    detached: false,
    windowsHide: true,
  });

  backendProcess.on('error', (err) => {
    console.error('Backend process error:', err);
  });

  backendProcess.on('exit', (code, signal) => {
    console.log(`Backend exited — code=${code} signal=${signal}`);
    backendProcess = null;
  });
}

function stopBackend() {
  if (!backendProcess) return;
  const pid = backendProcess.pid;
  backendProcess = null;
  try {
    // taskkill /F /T kills the process AND all its children (uvicorn workers etc.)
    // SIGTERM alone is not reliable on Windows for Python processes.
    if (process.platform === 'win32' && pid) {
      execSync(`taskkill /F /T /PID ${pid}`, { stdio: 'ignore' });
    } else {
      process.kill(pid, 'SIGTERM');
    }
  } catch (_) {}
}

// ── System tray ───────────────────────────────────────────────────────────────

function createTray() {
  // Fall back to an empty image if the icon file is missing
  const icon = appIcon.isEmpty()
    ? nativeImage.createEmpty()
    : appIcon.resize({ width: 16, height: 16 });

  tray = new Tray(icon);
  tray.setToolTip('VajraStocks — running in background');

  const menu = Menu.buildFromTemplate([
    {
      label: 'Open VajraStocks',
      click: () => showWindow(),
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => quitApp(),
    },
  ]);

  tray.setContextMenu(menu);
  tray.on('double-click', () => showWindow());
}

function showWindow() {
  if (!mainWindow) {
    createWindow();
    mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
  } else {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
  }
}

function quitApp() {
  isQuitting = true;
  stopBackend();
  app.quit();
}

// ── Window ────────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'VajraStocks',
    icon: appIcon,
    backgroundColor: '#0f1117',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false,
    },
  });

  Menu.setApplicationMenu(null);

  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(`http://127.0.0.1:${backendPort}`)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  // Close button → hide to tray, don't quit
  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault();
      mainWindow.hide();
      if (tray) tray.displayBalloon({
        iconType: 'info',
        title: 'VajraStocks',
        content: 'Running in background. Right-click the tray icon to quit.',
      });
    }
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── App boot sequence ─────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  if (process.platform === 'darwin' && app.dock && !appIcon.isEmpty()) {
    app.dock.setIcon(appIcon);
  }

  backendPort = await findFreePort(PREFERRED_PORT);

  createTray();
  createWindow();
  startBackend(backendPort);

  try {
    await waitForBackend(backendPort);
    if (mainWindow) mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
  } catch (err) {
    console.error('Backend failed to start:', err);
    if (mainWindow) mainWindow.loadFile(path.join(__dirname, 'error.html'));
  }
});

// With tray support the app must NOT quit when all windows are closed —
// the window is just hidden and the backend keeps running for scheduled jobs.
app.on('window-all-closed', () => {
  if (process.platform === 'darwin') app.quit();
  // Windows/Linux: stay alive in tray (do nothing)
});

app.on('activate', () => {
  // macOS dock click
  if (mainWindow === null) showWindow();
});

// Prevent multiple instances — focus existing window instead
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => showWindow());
}
