const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('petAPI', {
  getPetImage: (type) => ipcRenderer.invoke('get-pet-image', type),
  petDragStart: (offset) => ipcRenderer.invoke('pet-drag-start', offset),
  petDragMove: (x, y) => ipcRenderer.invoke('pet-drag-move', x, y),
  petDragEnd: () => ipcRenderer.invoke('pet-drag-end'),
  petClicked: () => ipcRenderer.invoke('pet-clicked'),
  getWakeWord: (characterId) => ipcRenderer.invoke('get-wake-word', characterId),
  asrStart: () => ipcRenderer.invoke('asr-start'),
  asrStop: () => ipcRenderer.invoke('asr-stop'),
  voiceResult: (text) => ipcRenderer.invoke('voice-result', text),
  kwsStart: () => ipcRenderer.invoke('kws-start'),
  kwsStop: () => ipcRenderer.invoke('kws-stop'),

  onVoiceBubble: (callback) => {
    ipcRenderer.on('voice-bubble', (event, data) => callback(data));
  },
  onEmotionChange: (callback) => {
    ipcRenderer.on('emotion-change', (event, emotion) => callback(emotion));
  },
  onUpdatePetImage: (callback) => {
    ipcRenderer.on('update-pet-image', (event, imageType) => callback(imageType));
  },
  onWakeWordDetected: (callback) => {
    ipcRenderer.on('wake-word-detected', (event, keyword) => callback(keyword));
  },
  onWakeWordListening: (callback) => {
    ipcRenderer.on('wake-word-listening', (event, listening) => callback(listening));
  },
  onWakeWordError: (callback) => {
    ipcRenderer.on('wake-word-error', (event, error) => callback(error));
  },
  onVoiceCommand: (callback) => {
    ipcRenderer.on('voice-command', (event, command) => callback(command));
  },
  onAsrReady: (callback) => {
    ipcRenderer.on('asr-ready', () => callback());
  },
  onAsrListening: (callback) => {
    ipcRenderer.on('asr-listening', (event, listening) => callback(listening));
  },
  onAsrPartial: (callback) => {
    ipcRenderer.on('asr-partial', (event, text) => callback(text));
  },
  onAsrResult: (callback) => {
    ipcRenderer.on('asr-result', (event, text) => callback(text));
  },
  onAsrError: (callback) => {
    ipcRenderer.on('asr-error', (event, error) => callback(error));
  },
});
