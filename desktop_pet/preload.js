const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  onVoiceChatResponse: (callback) => {
    ipcRenderer.on('voice-chat-response', (event, data) => callback(data));
  },
  onWindowShown: (callback) => {
    ipcRenderer.on('window-shown', () => callback());
  },
  getDesktopSession: () => ipcRenderer.invoke('get-desktop-session'),
  setDesktopSession: (sessionId) => ipcRenderer.invoke('set-desktop-session', sessionId)
});
