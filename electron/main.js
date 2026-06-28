'use strict';

const { app, BrowserWindow, shell, Menu, Tray, nativeImage } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');
const http = require('http');

// ── Configuration ─────────────────────────────────────────────────────────────

const PREFERRED_PORT = 8000;
const HEALTH_TIMEOUT_MS = 60_000;   // wait up to 60 s for backend
const HEALTH_POLL_MS    = 500;

// ── State ─────────────────────────────────────────────────────────────────────

let mainWindow = null;
let backendProcess = null;
let backendPort = PREFERRED_PORT;
let tray = null;

// ── Helpers ───────────────────────────────────────────────────────────────────

function findFreePort(preferred) {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(preferred, '127.0.0.1', () => {
      const { port } = server.address();
      server.close(() => resolve(port));
    });
    server.on('error', () => {
      // preferred port taken — let OS pick one
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
  // Dev mode — assume backend is already running externally
  return null;
}

// ── Backend lifecycle ─────────────────────────────────────────────────────────

function startBackend(port) {
  const exe = getBackendExe();
  if (!exe) return; // dev mode

  backendProcess = spawn(exe, [], {
    env: {
      ...process.env,
      VAJRA_PORT: String(port),
      VAJRA_ELECTRON: '1',          // tells launcher.py to skip webbrowser.open()
    },
    detached: false,
    windowsHide: true,              // no console window
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
  if (backendProcess) {
    try { backendProcess.kill('SIGTERM'); } catch (_) {}
    backendProcess = null;
  }
}

// ── Window ────────────────────────────────────────────────────────────────────

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: 'VajraStocks',
    // icon set after app ready via nativeImage
    backgroundColor: '#0f1117',
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  // Remove default menu bar (keep only system tray)
  Menu.setApplicationMenu(null);

  // Show loading screen immediately
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));
  mainWindow.once('ready-to-show', () => mainWindow.show());

  // Open external links in the OS browser, not inside the app
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (!url.startsWith(`http://127.0.0.1:${backendPort}`)) {
      shell.openExternal(url);
      return { action: 'deny' };
    }
    return { action: 'allow' };
  });

  mainWindow.on('closed', () => { mainWindow = null; });
}

// ── App boot sequence ─────────────────────────────────────────────────────────

app.whenReady().then(async () => {
  // Find a free port first so we own it
  backendPort = await findFreePort(PREFERRED_PORT);

  createWindow();
  startBackend(backendPort);

  try {
    await waitForBackend(backendPort);
    if (mainWindow) {
      mainWindow.loadURL(`http://127.0.0.1:${backendPort}`);
    }
  } catch (err) {
    console.error('Backend failed to start:', err);
    if (mainWindow) {
      mainWindow.loadFile(path.join(__dirname, 'error.html'));
    }
  }
});

app.on('window-all-closed', () => {
  stopBackend();
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (mainWindow === null) createWindow();
});

app.on('before-quit', stopBackend);

// Prevent multiple instances
const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });
}
