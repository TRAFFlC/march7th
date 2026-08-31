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
  setDesktopSession: (sessionId) => ipcRenderer.invoke('set-desktop-session', sessionId),

  // ===== Task 2: 后端健康监测 =====
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  onBackendStatus: (callback) => {
    ipcRenderer.on('backend-status', (event, status) => callback(status));
  },

  // ===== Task 3: 设置面板 =====
  getSettings: () => ipcRenderer.invoke('get-settings'),
  setSettings: (partial) => ipcRenderer.invoke('set-settings', partial),
  onSettingsChanged: (callback) => {
    ipcRenderer.on('settings-changed', (event, settings) => callback(settings));
  },

  // ===== Task 4: 消息通知与情绪联动 =====
  notifyMessage: (title, body) => ipcRenderer.invoke('notify-message', title, body),
  petEmotion: (emotion) => ipcRenderer.invoke('pet-emotion', emotion)
});
