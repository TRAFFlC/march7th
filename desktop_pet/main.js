const { app, BrowserWindow, Tray, Menu, ipcMain, nativeImage, screen, shell, Notification, globalShortcut } = require('electron');
const path = require('path');
const http = require('http');
const https = require('https');
const fs = require('fs');

const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
  console.log('[Main] 应用已在运行，退出...');
  app.quit();
} else {
  app.on('second-instance', () => {
    console.log('[Main] 检测到第二个实例启动，聚焦现有窗口');
    if (mainWindow && !mainWindow.isDestroyed()) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.show();
      mainWindow.focus();
    }
    showPetWindow();
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
let desktopSessionId = null;

// ===== 应用设置（Task 3 设置面板） =====
const DEFAULT_BACKEND_URL = 'http://127.0.0.1:8000';
const DEFAULT_SETTINGS = {
  streamingChat: true,        // Task 1: SSE 流式聊天
  autoPlayAudio: true,        // 自动播放语音回复
  notifyOnReply: true,        // Task 4: 桌面消息通知
  emotionSync: true,          // Task 4: 桌宠情绪联动
  wakeWordEnabled: true,      // 唤醒词检测
  idleInteraction: true,      // 空闲互动
  backendUrl: DEFAULT_BACKEND_URL,  // Task 11.1: 后端地址可配置
  globalShortcutEnabled: true,      // Task 11.2: 全局快捷键 Ctrl+Alt+M
  quietHoursEnabled: false,         // Task 11.3: 静音时段开关
  quietHoursStart: '23:00',         // Task 11.3: 静音开始时间
  quietHoursEnd: '08:00'            // Task 11.3: 静音结束时间
};
let appSettings = { ...DEFAULT_SETTINGS };

function getSettingsFilePath() {
  return path.join(app.getPath('userData'), 'pet_settings.json');
}

function loadSettings() {
  try {
    if (fs.existsSync(getSettingsFilePath())) {
      const saved = JSON.parse(fs.readFileSync(getSettingsFilePath(), 'utf-8'));
      appSettings = { ...DEFAULT_SETTINGS, ...saved };
    } else {
      // 首次运行时沿用 kws_config.json 中已有的唤醒词开关
      const kwsConfigPath = path.join(__dirname, 'kws_config.json');
      if (fs.existsSync(kwsConfigPath)) {
        const config = JSON.parse(fs.readFileSync(kwsConfigPath, 'utf-8'));
        appSettings.wakeWordEnabled = config.enabled !== false;
      }
    }
  } catch (e) {
    console.warn('[Main] 读取设置失败，使用默认设置:', e.message);
  }
}

function saveSettings() {
  try {
    fs.writeFileSync(getSettingsFilePath(), JSON.stringify(appSettings, null, 2));
  } catch (e) {
    console.warn('[Main] 保存设置失败:', e.message);
  }
}

function getSettingsForRenderer() {
  // autoStart 跟随系统实际状态，不落盘
  return { ...appSettings, autoStart: isAutoStartEnabled() };
}

// ===== Task 11.1: 后端地址解析（设置化，替换硬编码） =====
function normalizeBackendUrl(raw) {
  if (typeof raw !== 'string') return null;
  let s = raw.trim().replace(/\/+$/, '');
  if (!s) return null;
  if (!/^https?:\/\//i.test(s)) s = 'http://' + s;
  try {
    const u = new URL(s);
    if (!u.hostname) return null;
    return u.origin;
  } catch (e) {
    return null;
  }
}

function getParsedBackendUrl() {
  try {
    return new URL(appSettings.backendUrl || DEFAULT_BACKEND_URL);
  } catch (e) {
    return new URL(DEFAULT_BACKEND_URL);
  }
}

function backendHttpModule() {
  return getParsedBackendUrl().protocol === 'https:' ? https : http;
}

// 为 http/https.request 生成指向当前后端地址的连接参数
function backendConnectionOptions() {
  const u = getParsedBackendUrl();
  return {
    hostname: u.hostname,
    port: u.port || (u.protocol === 'https:' ? 443 : 80)
  };
}

function broadcastSettings() {
  const settings = getSettingsForRenderer();
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('settings-changed', settings);
  }
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('settings-changed', settings);
  }
}

function applySettings(changedKeys, partial) {
  if (changedKeys.includes('wakeWordEnabled') && kwsDetector) {
    if (appSettings.wakeWordEnabled) {
      if (petWindow && !petWindow.isDestroyed()) {
        kwsDetector.startListening(petWindow).catch(() => {});
      }
    } else {
      kwsDetector.stopListening();
    }
  }
  if (changedKeys.includes('autoStart') && typeof partial.autoStart === 'boolean') {
    setAutoStart(partial.autoStart);
  }
  if (changedKeys.includes('emotionSync')) {
    if (appSettings.emotionSync) {
      ensureEmotionStream();
    } else {
      stopEmotionStream();
    }
  }
  // Task 11.2: 全局快捷键开关注册/注销
  if (changedKeys.includes('globalShortcutEnabled')) {
    if (appSettings.globalShortcutEnabled) {
      registerChatShortcut();
    } else {
      unregisterChatShortcut();
    }
  }
  // Task 11.1: 后端地址修改后立即生效（健康监测与情绪流切换到新地址）
  if (changedKeys.includes('backendUrl')) {
    backendConsecutiveFailures = 0;
    stopEmotionStream();
    pollBackendHealth().then(() => {
      if (backendOnline) ensureEmotionStream();
    });
  }
}

function updateSettings(partial) {
  if (!partial || typeof partial !== 'object') return getSettingsForRenderer();
  const changedKeys = [];
  for (const [key, rawValue] of Object.entries(partial)) {
    let value = rawValue;
    if (key === 'backendUrl') {
      value = normalizeBackendUrl(rawValue);
      if (!value) continue; // 非法地址直接忽略
    }
    if (key in DEFAULT_SETTINGS && typeof value === typeof DEFAULT_SETTINGS[key]) {
      if (appSettings[key] !== value) {
        appSettings[key] = value;
        changedKeys.push(key);
      }
    } else if (key === 'autoStart' && typeof value === 'boolean') {
      changedKeys.push(key);
    }
  }
  if (changedKeys.length) {
    saveSettings();
    applySettings(changedKeys, partial);
    broadcastSettings();
  }
  return getSettingsForRenderer();
}

// ===== 后端健康监测（Task 2） =====
let backendOnline = false;
let backendConsecutiveFailures = 0;
const HEALTH_CHECK_INTERVAL = 10000;

function checkBackendHealth() {
  return new Promise((resolve) => {
    const req = backendHttpModule().request(Object.assign(backendConnectionOptions(), {
      path: '/',
      method: 'GET',
      timeout: 4000
    }), (res) => {
      res.resume();
      resolve(!!res.statusCode && res.statusCode < 500);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
    req.end();
  });
}

function broadcastBackendStatus() {
  const status = { online: backendOnline };
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('backend-status', status);
  }
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('backend-status', status);
  }
}

function setBackendOnline(online) {
  if (backendOnline === online) return;
  backendOnline = online;
  console.log('[Health] 后端服务状态变更:', online ? '在线' : '离线');
  broadcastBackendStatus();
  if (tray && !tray.isDestroyed()) {
    tray.setToolTip(online ? '七音盒 - 桌宠' : '七音盒 - 桌宠（后端离线）');
  }
  if (appSettings.notifyOnReply) {
    showAppNotification(
      '七音盒',
      online ? '后端服务已恢复连接' : '后端服务连接中断，聊天功能暂不可用'
    );
  }
  if (online) {
    ensureEmotionStream();
  } else {
    stopEmotionStream();
  }
}

async function pollBackendHealth() {
  const ok = await checkBackendHealth();
  if (ok) {
    backendConsecutiveFailures = 0;
    setBackendOnline(true);
  } else {
    backendConsecutiveFailures += 1;
    // 连续两次失败才判定离线，避免网络抖动误报
    if (backendConsecutiveFailures >= 2) {
      setBackendOnline(false);
    }
  }
}

function startHealthMonitor() {
  setInterval(pollBackendHealth, HEALTH_CHECK_INTERVAL);
  pollBackendHealth();
}

// ===== 桌面通知（Task 4 消息通知） =====
function showAppNotification(title, body) {
  if (!appSettings.notifyOnReply) return false;
  if (!Notification.isSupported()) return false;
  try {
    const notification = new Notification({ title, body });
    notification.on('click', () => showChatWindow());
    notification.show();
    return true;
  } catch (e) {
    console.warn('[Notify] 通知显示失败:', e.message);
    return false;
  }
}

// ===== 情绪联动（Task 4）：订阅后端 /api/pet/emotion SSE，驱动桌宠表情 =====
const EMOTION_IMAGE_MAP = {
  neutral: 'normal',
  happy: 'happy',
  confused: 'thinking',
  sad: 'sad',        // Task 11.6: sad/angry 映射到差异化表情图
  angry: 'angry',
  excited: 'surprised'
};
let emotionStreamReq = null;
let emotionStreamActive = false;

function applyPetEmotion(emotion) {
  if (!emotion) return;
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.webContents.send('emotion-change', emotion);
    petWindow.webContents.send('update-pet-image', EMOTION_IMAGE_MAP[emotion] || 'normal');
  }
}

function stopEmotionStream() {
  if (emotionStreamReq) {
    emotionStreamReq.destroy();
    emotionStreamReq = null;
  }
  emotionStreamActive = false;
}

function openEmotionStream(authToken) {
  emotionStreamActive = true;
  const req = backendHttpModule().request(Object.assign(backendConnectionOptions(), {
    path: '/api/pet/emotion',
    method: 'GET',
    headers: { 'Authorization': `Bearer ${authToken}` }
  }), (res) => {
    if (res.statusCode === 401) {
      console.log('[Emotion] Token 无效，暂停情绪联动，等待重新登录');
      emotionStreamActive = false;
      emotionStreamReq = null;
      res.resume();
      return;
    }
    let buffer = '';
    res.on('data', (chunk) => {
      buffer += chunk.toString();
      let idx;
      while ((idx = buffer.indexOf('\n')) !== -1) {
        const line = buffer.slice(0, idx).trim();
        buffer = buffer.slice(idx + 1);
        if (line.startsWith('data: ')) {
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.emotion) applyPetEmotion(payload.emotion);
          } catch (e) {}
        }
      }
    });
    const onStreamEnd = () => {
      emotionStreamActive = false;
      emotionStreamReq = null;
    };
    res.on('end', onStreamEnd);
    res.on('error', onStreamEnd);
  });
  req.on('error', (e) => {
    console.log('[Emotion] 情绪流连接失败:', e.message);
    emotionStreamActive = false;
    emotionStreamReq = null;
  });
  emotionStreamReq = req;
  req.end();
}

function ensureEmotionStream() {
  if (emotionStreamActive || !appSettings.emotionSync || !backendOnline) return;
  const authToken = readSharedToken();
  if (!authToken) return;
  openEmotionStream(authToken);
}

const EMOJIS_DIR = path.join(__dirname, '..', 'frontend', 'public', 'emojis');

const PET_IMAGES = {
  normal: path.join(EMOJIS_DIR, '三月七_盯.png'),
  happy: path.join(EMOJIS_DIR, '三月七_开心.png'),
  thinking: path.join(EMOJIS_DIR, '三月七_暗中观察.png'),
  surprised: path.join(EMOJIS_DIR, '三月七_biu.png'),
  sad: path.join(EMOJIS_DIR, '三月七_哭.png'),       // Task 11.6
  angry: path.join(EMOJIS_DIR, '三月七_生气.png')    // Task 11.6
};

const SHARED_TOKEN_PATH = path.join(__dirname, '..', 'shared_token.json');

// ===== 常驻状态持久化 =====
const PET_SIZE = { width: 120, height: 200 };
let petState = { petX: null, petY: null };

function getStateFilePath() {
  return path.join(app.getPath('userData'), 'pet_state.json');
}

function loadPetState() {
  try {
    if (fs.existsSync(getStateFilePath())) {
      const saved = JSON.parse(fs.readFileSync(getStateFilePath(), 'utf-8'));
      if (typeof saved.petX === 'number' && typeof saved.petY === 'number') {
        petState = { petX: saved.petX, petY: saved.petY };
      }
    }
  } catch (e) {
    console.warn('[Main] 读取桌宠状态失败:', e.message);
  }
}

function savePetState() {
  try {
    fs.writeFileSync(getStateFilePath(), JSON.stringify(petState, null, 2));
  } catch (e) {
    console.warn('[Main] 保存桌宠状态失败:', e.message);
  }
}

function persistPetPosition() {
  if (petWindow && !petWindow.isDestroyed()) {
    const [x, y] = petWindow.getPosition();
    petState.petX = x;
    petState.petY = y;
    savePetState();
  }
}

function isPetPositionVisible(x, y) {
  // 校验位置在任一显示器的可见工作区内（应对分辨率变化/显示器移除）
  return screen.getAllDisplays().some((display) => {
    const area = display.workArea;
    return x >= area.x &&
           y >= area.y &&
           x + PET_SIZE.width <= area.x + area.width &&
           y + PET_SIZE.height <= area.y + area.height;
  });
}

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

    const req = backendHttpModule().request(options, (res) => {
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

  let x = width - 150;
  let y = height - 230;

  if (petState.petX !== null && petState.petY !== null) {
    if (isPetPositionVisible(petState.petX, petState.petY)) {
      x = petState.petX;
      y = petState.petY;
      console.log('[Main] 恢复桌宠上次位置:', x, y);
    } else {
      console.log('[Main] 保存的桌宠位置超出可见屏幕范围，使用默认位置');
    }
  }

  petWindow = new BrowserWindow({
    width: PET_SIZE.width,
    height: PET_SIZE.height,
    x,
    y,
    show: true,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    resizable: false,
    skipTaskbar: true,
    focusable: true,
    hasShadow: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: true,
      preload: path.join(__dirname, 'pet_preload.js')
    }
  });

  petWindow.loadFile(path.join(__dirname, 'src', 'pet.html'));

  // 窗口（重）建后同步当前后端状态与应用设置
  petWindow.webContents.on('did-finish-load', () => {
    petWindow.webContents.send('backend-status', { online: backendOnline });
    petWindow.webContents.send('settings-changed', getSettingsForRenderer());
  });

  // petWindow.webContents.openDevTools({ mode: 'detach' });

  petWindow.on('close', (event) => {
    // 常驻模式：关闭窗口只隐藏到托盘，不销毁
    if (!isQuitting) {
      event.preventDefault();
      petWindow.hide();
      persistPetPosition();
    }
  });

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

  // 窗口（重）建后同步当前后端状态与应用设置
  mainWindow.webContents.on('did-finish-load', () => {
    mainWindow.webContents.send('backend-status', { online: backendOnline });
    mainWindow.webContents.send('settings-changed', getSettingsForRenderer());
  });

  // Task 11.5: 窗口显示后停止任务栏/托盘闪烁
  mainWindow.on('show', () => {
    mainWindow.flashFrame(false);
  });

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
}

// ===== 开机自启动 =====
function getLoginItemArgs() {
  // 开发模式下以 `electron .` 运行，注册启动命令时需要带上项目目录参数
  return app.isPackaged ? [] : [path.resolve(__dirname)];
}

function setAutoStart(enabled) {
  try {
    app.setLoginItemSettings({
      openAtLogin: enabled,
      path: process.execPath,
      args: getLoginItemArgs()
    });
    console.log('[Main] 开机自启动已' + (enabled ? '开启' : '关闭'));
  } catch (e) {
    console.error('[Main] 设置开机自启动失败:', e.message);
  }
}

function isAutoStartEnabled() {
  try {
    const settings = app.getLoginItemSettings({
      path: process.execPath,
      args: getLoginItemArgs()
    });
    return !!settings.openAtLogin;
  } catch (e) {
    return false;
  }
}

// ===== 窗口生命周期辅助 =====
function showPetWindow() {
  if (isQuitting) return;
  if (!petWindow || petWindow.isDestroyed()) {
    createPetWindow();
    // 窗口重建后，重新绑定唤醒词检测的事件目标
    if (kwsDetector && petWindow && !petWindow.isDestroyed()) {
      kwsDetector.setWindow(petWindow);
    }
  }
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.show();
  }
}

function positionChatWindowNearPet() {
  if (!mainWindow || mainWindow.isDestroyed()) return;
  if (petWindow && !petWindow.isDestroyed()) {
    const petBounds = petWindow.getBounds();
    const chatBounds = mainWindow.getBounds();
    const workArea = screen.getDisplayMatching(petBounds).workArea;

    let x = petBounds.x - chatBounds.width - 20;
    if (x < workArea.x) {
      // 桌宠贴近屏幕左边缘时，聊天窗口改放右侧
      x = petBounds.x + petBounds.width + 20;
    }
    let y = petBounds.y - PET_SIZE.height;

    x = Math.min(Math.max(x, workArea.x), workArea.x + workArea.width - chatBounds.width);
    y = Math.min(Math.max(y, workArea.y), workArea.y + workArea.height - chatBounds.height);

    mainWindow.setPosition(Math.round(x), Math.round(y));
  } else {
    mainWindow.center();
  }
}

function showChatWindow() {
  if (isQuitting) return;
  if (!mainWindow || mainWindow.isDestroyed()) {
    createChatWindow();
  }
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    positionChatWindowNearPet();
    mainWindow.show();
    mainWindow.focus();
    mainWindow.flashFrame(false); // Task 11.5: 展示窗口后停止闪烁
    mainWindow.webContents.send('window-shown');
  }
}

function hideChatWindow() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.hide();
  }
}

function toggleChatWindow() {
  if (mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible()) {
    hideChatWindow();
  } else {
    showChatWindow();
  }
}

// ===== Task 11.2: 全局快捷键 Ctrl+Alt+M 切换聊天窗口 =====
const TOGGLE_CHAT_ACCELERATOR = 'Ctrl+Alt+M';

function registerChatShortcut() {
  if (globalShortcut.isRegistered(TOGGLE_CHAT_ACCELERATOR)) return;
  try {
    const ok = globalShortcut.register(TOGGLE_CHAT_ACCELERATOR, toggleChatWindow);
    console.log(ok ? '[Main] 全局快捷键已注册: ' + TOGGLE_CHAT_ACCELERATOR
                   : '[Main] 全局快捷键注册失败（可能被占用）: ' + TOGGLE_CHAT_ACCELERATOR);
  } catch (e) {
    console.warn('[Main] 全局快捷键注册异常:', e.message);
  }
}

function unregisterChatShortcut() {
  try {
    if (globalShortcut.isRegistered(TOGGLE_CHAT_ACCELERATOR)) {
      globalShortcut.unregister(TOGGLE_CHAT_ACCELERATOR);
      console.log('[Main] 全局快捷键已注销:', TOGGLE_CHAT_ACCELERATOR);
    }
  } catch (e) {}
}

function quitApp() {
  isQuitting = true;
  persistPetPosition();
  stopEmotionStream();
  unregisterChatShortcut(); // Task 11.2: 退出前释放全局快捷键
  if (tray) {
    tray.removeAllListeners();
    tray.destroy();
    tray = null;
  }
  app.quit();
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
      click: () => showChatWindow()
    },
    {
      label: '显示桌宠',
      click: () => showPetWindow()
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
      label: '开机自启动',
      type: 'checkbox',
      checked: isAutoStartEnabled(),
      click: (menuItem) => setAutoStart(menuItem.checked)
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
      click: () => quitApp()
    }
  ]);

  tray.setToolTip('七音盒 - 桌宠');
  tray.setContextMenu(contextMenu);

  tray.on('click', () => {
    if (isQuitting || !tray) return;
    toggleChatWindow();
  });

  tray.on('double-click', () => {
    if (isQuitting || !tray) return;
    showPetWindow();
  });
}

app.whenReady().then(async () => {
  loadPetState();
  loadSettings();
  // Windows 桌面通知需要稳定的 AppUserModelID
  if (process.platform === 'win32') {
    app.setAppUserModelId('com.march7th.desktop-pet');
  }
  createPetWindow();
  createChatWindow();
  createTray();

  // Task 2: 后端健康监测
  startHealthMonitor();
  // Task 4: 情绪联动长连接的兜底重连（Token 生成 / 后端恢复后自动补连）
  setInterval(ensureEmotionStream, 30000);
  ensureEmotionStream();

  // Task 11.2: 按设置注册全局快捷键
  if (appSettings.globalShortcutEnabled) {
    registerChatShortcut();
  }

  if (kwsDetector) {
    kwsDetector.setupIpcHandlers();
    
    if (appSettings.wakeWordEnabled) {
      setTimeout(async () => {
        if (petWindow && !petWindow.isDestroyed()) {
          console.log('[Main] 自动启动唤醒词检测...');
          await kwsDetector.startListening(petWindow);
        }
      }, 2000);
    } else {
      console.log('[Main] 唤醒词检测已在设置中关闭，跳过启动');
    }
  }
  
  if (asrDetector) {
    asrDetector.setupIpcHandlers();
  }
});

app.on('window-all-closed', () => {
  // 常驻模式：窗口全部关闭后仍驻留托盘，仅能通过托盘菜单退出
});

app.on('will-quit', () => {
  // Task 11.2: 释放所有全局快捷键
  try { globalShortcut.unregisterAll(); } catch (e) {}
});

app.on('before-quit', () => {
  isQuitting = true;
  persistPetPosition();
  stopEmotionStream();
  unregisterChatShortcut(); // Task 11.2
  if (tray) {
    tray.removeAllListeners();
    tray.destroy();
    tray = null;
  }
});

ipcMain.handle('get-api-base', () => appSettings.backendUrl || DEFAULT_BACKEND_URL);

// ===== Task 2: 后端健康状态查询 =====
ipcMain.handle('get-backend-status', () => ({ online: backendOnline }));

// ===== Task 3: 设置读写 =====
ipcMain.handle('get-settings', () => getSettingsForRenderer());

ipcMain.handle('set-settings', (event, partial) => updateSettings(partial));

// ===== Task 4: 渲染进程请求桌面通知（仅聊天窗口不可见时真正弹出） =====
ipcMain.handle('notify-message', (event, title, body) => {
  const chatVisible = mainWindow && !mainWindow.isDestroyed() && mainWindow.isVisible();
  if (chatVisible) {
    return { success: true, shown: false };
  }
  // Task 11.5: 聊天窗口隐藏时回复到达，闪烁任务栏提醒
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.flashFrame(true);
  }
  const shown = showAppNotification(title || '七音盒', body || '');
  return { success: true, shown };
});

ipcMain.handle('get-wake-word', async (event, characterId) => {
  const charId = characterId || 'march7th';
  
  try {
    const response = await httpRequest(Object.assign(backendConnectionOptions(), {
      path: `/api/characters/${charId}/wake-word`,
      method: 'GET',
      timeout: 5000
    }));

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
  if (isQuitting) return { success: true };
  toggleChatWindow();
  return { success: true };
});

ipcMain.handle('pet-drag-start', (event, offset) => {
  isDragging = true;
  dragOffset = offset;
});

ipcMain.handle('pet-drag-end', () => {
  isDragging = false;
  persistPetPosition();
  return true;
});

ipcMain.handle('pet-drag-move', (event, screenX, screenY) => {
  if (isDragging && petWindow && !petWindow.isDestroyed()) {
    const newX = Math.round(screenX - dragOffset.x);
    const newY = Math.round(screenY - dragOffset.y);
    petWindow.setPosition(newX, newY);
  }
});

ipcMain.handle('pet-emotion', (event, emotion) => {
  applyPetEmotion(emotion);
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

    const response = await httpRequest(Object.assign(backendConnectionOptions(), {
      path: '/api/voice/input',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': Buffer.byteLength(postData)
      },
      timeout: 120000
    }), postData);

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
          showChatWindow();
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
