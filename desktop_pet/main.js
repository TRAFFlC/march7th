const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, screen, shell } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  console.log('[Main] 应用已在运行，退出...');
  app.quit();
} else {
  app.on('second-instance', () => {
    console.log('[Main] 检测到第二个实例启动，聚焦现有窗口');
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
    if (petWindow) {
      petWindow.show();
    }
  });
}

let kwsDetector = null;
try {
  kwsDetector = require('./kws_detector');
  console.log('[Main] 唤醒词检测模块加载成功');
} catch (e) {
  console.log('[Main] 唤醒词检测模块未安装，跳过:', e.message);
}

let asrDetector = null;
try {
  asrDetector = require('./asr_detector');
  console.log('[Main] 语音识别模块加载成功');
} catch (e) {
  console.log('[Main] 语音识别模块未安装，跳过:', e.message);
}

let mainWindow = null;
let petWindow = null;
let tray = null;
let isQuitting = false;
let isDragging = false;
let dragOffset = { x: 0, y: 0 };
let kwsEnabled = false;
let desktopSessionId = null;

const EMOJIS_DIR = path.join(__dirname, '..', 'frontend', 'public', 'emojis');

const PET_IMAGES = {
  normal: path.join(EMOJIS_DIR, '三月七_盯.png'),
  happy: path.join(EMOJIS_DIR, '三月七_开心.png'),
  thinking: path.join(EMOJIS_DIR, '三月七_暗中观察.png'),
  surprised: path.join(EMOJIS_DIR, '三月七_biu.png')
};

const API_BASE = 'http://127.0.0.1:8000';
const SHARED_TOKEN_PATH = path.join(__dirname, '..', 'shared_token.json');

function readSharedToken() {
  try {
    if (fs.existsSync(SHARED_TOKEN_PATH)) {
      const tokenData = JSON.parse(fs.readFileSync(SHARED_TOKEN_PATH, 'utf-8'));
      return tokenData.token || '';
    }
  } catch (e) {}
  return '';
}

function httpRequest(options, body = null) {
  return new Promise((resolve, reject) => {
    const authToken = readSharedToken();
    options.headers = options.headers || {};
    if (authToken) {
      options.headers['Authorization'] = `Bearer ${authToken}`;
    }

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        console.log('[Main] HTTP 状态码:', res.statusCode);
        console.log('[Main] 响应数据长度:', data.length);
        console.log('[Main] 响应数据前200字符:', data.substring(0, 200));

        if (res.statusCode === 401) {
          console.log('[Main] Token 无效或已过期，请在网页端重新登录');
          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('auth-expired');
          }
          if (petWindow && !petWindow.isDestroyed()) {
            petWindow.webContents.send('auth-expired');
          }
        }

        resolve({ statusCode: res.statusCode, data: data });
      });
    });

    req.on('error', reject);
    req.setTimeout(options.timeout || 30000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });

    if (body) {
      req.write(body);
    }
    req.end();
  });
}

function createPetWindow() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize;
  
  petWindow = new BrowserWindow({
    width: 120,
    height: 200,
    x: width - 150,
    y: height - 230,
    show: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    focusable: true,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      webSecurity: false
    }
  });

  petWindow.loadFile(path.join(__dirname, 'src', 'pet.html'));
  
  // petWindow.webContents.openDevTools({ mode: 'detach' });

  petWindow.on('closed', () => {
    petWindow = null;
  });
}

function createChatWindow() {
  mainWindow = new BrowserWindow({
    width: 400,
    height: 500,
    show: false,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  mainWindow.loadFile(path.join(__dirname, 'src', 'chat.html'));

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

function createTray() {
  if (tray) {
    tray.removeAllListeners();
    tray.destroy();
    tray = null;
  }

  const icon = nativeImage.createFromPath(PET_IMAGES.normal);
  const trayIcon = icon.resize({ width: 64, height: 64 });

  tray = new Tray(trayIcon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: '打开聊天',
      click: () => {
        if (mainWindow && !mainWindow.isDestroyed() && !isQuitting) {
          mainWindow.show();
          mainWindow.center();
        }
      }
    },
    {
      label: '显示桌宠',
      click: () => {
        if (petWindow && !petWindow.isDestroyed() && !isQuitting) {
          petWindow.show();
        }
      }
    },
    {
      label: '隐藏桌宠',
      click: () => {
        if (petWindow && !petWindow.isDestroyed() && !isQuitting) {
          petWindow.hide();
        }
      }
    },
    { type: 'separator' },
    {
      label: '网页端登录',
      click: () => {
        shell.openExternal('http://localhost:5173');
      }
    },
    { type: 'separator' },
    {
      label: '退出',
      click: () => {
        isQuitting = true;
        if (tray) {
          tray.removeAllListeners();
          tray.destroy();
          tray = null;
        }
        app.quit();
      }
    }
  ]);

  tray.setToolTip('七音盒 - 桌宠');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (isQuitting || !tray) return;
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isVisible()) {
        mainWindow.hide();
      } else {
        mainWindow.show();
        mainWindow.center();
      }
    }
  });
}

app.whenReady().then(async () => {
  createPetWindow();
  createChatWindow();
  createTray();
  
  if (kwsDetector) {
    kwsDetector.setupIpcHandlers();
    
    const kwsConfigPath = path.join(__dirname, 'kws_config.json');
    if (fs.existsSync(kwsConfigPath)) {
      try {
        const config = JSON.parse(fs.readFileSync(kwsConfigPath, 'utf-8'));
        kwsEnabled = config.enabled !== false;
      } catch (e) {
        kwsEnabled = true;
      }
    } else {
      kwsEnabled = true;
    }
    
    if (kwsEnabled) {
      setTimeout(async () => {
        if (petWindow && !petWindow.isDestroyed()) {
          console.log('[Main] 自动启动唤醒词检测...');
          await kwsDetector.startListening(petWindow);
        }
      }, 2000);
    }
  }
  
  if (asrDetector) {
    asrDetector.setupIpcHandlers();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    isQuitting = true;
    if (tray) {
      tray.removeAllListeners();
      tray.destroy();
      tray = null;
    }
    app.quit();
  }
});

app.on('before-quit', () => {
  isQuitting = true;
  if (tray) {
    tray.removeAllListeners();
    tray.destroy();
    tray = null;
  }
});

ipcMain.handle('get-api-base', () => API_BASE);

ipcMain.handle('get-wake-word', async (event, characterId) => {
  const charId = characterId || 'march7th';
  
  try {
    const response = await httpRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: `/api/characters/${charId}/wake-word`,
      method: 'GET',
      timeout: 5000
    });

    if (response.statusCode >= 400) {
      return { success: false, wakeWord: '三月七', error: `HTTP ${response.statusCode}` };
    }

    try {
      const parsed = JSON.parse(response.data);
      if (parsed.success && parsed.wake_word) {
        return { success: true, wakeWord: parsed.wake_word };
      }
    } catch (e) {}
    
    return { success: false, wakeWord: '三月七' };
  } catch (e) {
    return { success: false, wakeWord: '三月七', error: e.message };
  }
});

ipcMain.handle('minimize-window', () => {
  if (mainWindow && !isQuitting) mainWindow.hide();
});

ipcMain.handle('get-pet-image', (event, type) => {
  const imagePath = PET_IMAGES[type] || PET_IMAGES.normal;
  return 'file:///' + imagePath.replace(/\\/g, '/');
});

ipcMain.handle('get-desktop-session', () => {
  return desktopSessionId;
});

ipcMain.handle('set-desktop-session', (event, sessionId) => {
  desktopSessionId = sessionId;
  console.log('[Main] 桌宠会话ID已更新:', desktopSessionId);
  return true;
});

ipcMain.handle('pet-clicked', () => {
  if (mainWindow && !isQuitting && !mainWindow.isDestroyed()) {
    if (mainWindow.isVisible()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      if (petWindow && !petWindow.isDestroyed()) {
        const petBounds = petWindow.getBounds();
        mainWindow.setPosition(petBounds.x - 420, petBounds.y - 200);
      } else {
        mainWindow.center();
      }
      mainWindow.webContents.send('window-shown');
    }
  } else if (!mainWindow || mainWindow.isDestroyed()) {
    createChatWindow();
    if (mainWindow) {
      mainWindow.show();
      mainWindow.center();
      mainWindow.webContents.send('window-shown');
    }
  }
});

ipcMain.handle('pet-drag-start', (event, offset) => {
  isDragging = true;
  dragOffset = offset;
});

ipcMain.handle('pet-drag-end', () => {
  isDragging = false;
});

ipcMain.handle('pet-drag-move', (event, screenX, screenY) => {
  if (isDragging && petWindow && !petWindow.isDestroyed()) {
    const newX = Math.round(screenX - dragOffset.x);
    const newY = Math.round(screenY - dragOffset.y);
    petWindow.setPosition(newX, newY);
  }
});

ipcMain.handle('pet-emotion', (event, emotion) => {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('emotion-change', emotion);
  }
  const emotionMap = {
    neutral: 'normal',
    happy: 'happy',
    confused: 'thinking',
    sad: 'normal',
    angry: 'normal',
    excited: 'surprised'
  };
  const imageType = emotionMap[emotion] || 'normal';
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('update-pet-image', imageType);
  }
  return { success: true, emotion: emotion };
});

if (kwsDetector) {
  ipcMain.on('wake-word-detected', (event, keyword) => {
    console.log('[Main] 收到唤醒词检测事件:', keyword);
    if (petWindow && !petWindow.isDestroyed()) {
      petWindow.webContents.send('wake-word-detected', keyword);
    }
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('wake-word-detected', keyword);
    }
  });

  ipcMain.on('wake-word-listening', (event, listening) => {
    console.log('[Main] 唤醒词监听状态:', listening);
    if (petWindow && !petWindow.isDestroyed()) {
      petWindow.webContents.send('wake-word-listening', listening);
    }
  });

  ipcMain.on('wake-word-error', (event, error) => {
    console.error('[Main] 唤醒词错误:', error);
    if (petWindow && !petWindow.isDestroyed()) {
      petWindow.webContents.send('wake-word-error', error);
    }
  });
}

ipcMain.handle('start-voice-listening', () => {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('voice-command', 'start');
  }
  return { success: true };
});

ipcMain.handle('stop-voice-listening', () => {
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('voice-command', 'stop');
  }
  return { success: true };
});

ipcMain.handle('voice-result', async (event, text) => {
  if (!text || !text.trim()) return { success: false, error: 'Empty text' };

  try {
    const requestBody = {
      message: text.trim(),
      character_id: 'march7th'
    };
    if (desktopSessionId) {
      requestBody.session_id = desktopSessionId;
    }

    const postData = JSON.stringify(requestBody);

    const response = await httpRequest({
      hostname: '127.0.0.1',
      port: 8000,
      path: '/api/voice/input',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      },
      timeout: 120000
    }, postData);

    if (response.statusCode >= 400) {
      console.log('[Main] voice-result HTTP 错误:', response.statusCode);
      return { success: false, error: `HTTP ${response.statusCode}` };
    }

    let result;
    try {
      result = JSON.parse(response.data);
      console.log('[Main] voice-result 解析后 success:', result.success);
      console.log('[Main] voice-result 解析后 response:', result.response ? `存在，长度 ${result.response.length}` : '不存在或为空');
      console.log('[Main] voice-result 解析后 session_id:', result.session_id);
    } catch (e) {
      console.error('[Main] voice-result JSON 解析失败:', e.message);
      return { success: false, error: 'Invalid response' };
    }

    if (result.success && result.response) {
      console.log('[Main] 语音处理成功，response长度:', result.response.length);
      console.log('[Main] 音频数据:', result.audio ? `存在，长度 ${result.audio.length}` : '不存在');

      if (result.session_id) {
        desktopSessionId = result.session_id;
        console.log('[Main] 更新桌宠会话ID:', desktopSessionId);
      }

      if (mainWindow && !mainWindow.isDestroyed()) {
        if (!mainWindow.isVisible()) {
          console.log('[Main] 聊天窗口未显示，自动显示');
          mainWindow.show();
          if (petWindow && !petWindow.isDestroyed()) {
            const petBounds = petWindow.getBounds();
            mainWindow.setPosition(petBounds.x - 420, petBounds.y - 200);
          }
        }
        mainWindow.webContents.send('voice-chat-response', {
          userText: text,
          response: result.response,
          audio: result.audio,
          session_id: result.session_id
        });
        console.log('[Main] 已发送 voice-chat-response 到聊天窗口');
      }

      if (petWindow && !petWindow.isDestroyed()) {
        petWindow.webContents.send('voice-bubble', {
          text: result.response,
          audio: result.audio,
          chatWindowVisible: mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()
        });
        console.log('[Main] 已发送 voice-bubble 到桌宠窗口');
      }
    } else {
      console.log('[Main] 语音处理失败:', result);
    }

    return result;
  } catch (e) {
    return { success: false, error: e.message };
  }
});
