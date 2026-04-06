const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("slideshowApi", {
  pickFolder: () => ipcRenderer.invoke("dialog:pick-folder"),
  getConfig: () => ipcRenderer.invoke("app:get-config"),
  startSlideshow: (payload) => ipcRenderer.invoke("slideshow:start", payload),
  cancelSlideshow: () => ipcRenderer.invoke("slideshow:cancel"),
  onProgress: (handler) => {
    const listener = (_event, data) => handler(data);
    ipcRenderer.on("slideshow:progress", listener);
    return () => ipcRenderer.removeListener("slideshow:progress", listener);
  },
  onDone: (handler) => {
    const listener = (_event, data) => handler(data);
    ipcRenderer.on("slideshow:done", listener);
    return () => ipcRenderer.removeListener("slideshow:done", listener);
  },
  onError: (handler) => {
    const listener = (_event, data) => handler(data);
    ipcRenderer.on("slideshow:error", listener);
    return () => ipcRenderer.removeListener("slideshow:error", listener);
  }
});
