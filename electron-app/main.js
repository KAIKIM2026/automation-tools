const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const path = require("path");
const { startSlideshowJob, cancelSlideshowJob, hasActiveJob } = require("./src/main/slideshow-service");

const APP_ROOT = __dirname;
const PROJECT_ROOT = path.resolve(APP_ROOT, "..");

let mainWindow = null;

function relay(channel, data) {
  if (!mainWindow || mainWindow.isDestroyed()) {
    return;
  }
  mainWindow.webContents.send(channel, data);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1080,
    height: 1040,
    minWidth: 1080,
    minHeight: 1040,
    maxWidth: 1080,
    maxHeight: 1040,
    backgroundColor: "#eaf5fb",
    title: "Slideshow Studio",
    icon: path.join(APP_ROOT, "assets", "icons", "app-icon.png"),
    resizable: false,
    maximizable: false,
    fullscreenable: false,
    webPreferences: {
      preload: path.join(APP_ROOT, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.loadFile(path.join(APP_ROOT, "renderer", "index.html"));
}

ipcMain.handle("dialog:pick-folder", async () => {
  if (!mainWindow) {
    return "";
  }

  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ["openDirectory"]
  });

  if (result.canceled || result.filePaths.length === 0) {
    return "";
  }

  return result.filePaths[0];
});

ipcMain.handle("app:get-config", async () => ({
  projectRoot: PROJECT_ROOT,
  ffmpegPath: path.join(PROJECT_ROOT, "ffmpeg-8.1-essentials_build", "bin", "ffmpeg.exe"),
  busy: hasActiveJob()
}));

ipcMain.handle("slideshow:start", async (_event, payload) => startSlideshowJob(payload, {
  projectRoot: PROJECT_ROOT,
  sendProgress: (data) => relay("slideshow:progress", data),
  sendDone: (data) => relay("slideshow:done", data),
  sendError: (data) => relay("slideshow:error", data)
}));

ipcMain.handle("slideshow:cancel", async () => {
  cancelSlideshowJob();
  return { ok: true };
});

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
