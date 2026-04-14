/**
 * Sherpa-ONNX 唤醒词检测模块
 * 使用 Python 子进程实现唤醒词检测
 */

const { ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let kwsProcess = null;
let isListening = false;
let mainWindow = null;

const MODELS_DIR = path.resolve(__dirname, 'models');
const KWS_SCRIPT = path.join(MODELS_DIR, 'kws_service.py');

function getPythonPath() {
    const possiblePaths = [
        'python',
        'python3',
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python311', 'python.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python310', 'python.exe'),
        path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Python', 'Python39', 'python.exe'),
    ];
    
    for (const p of possiblePaths) {
        try {
            const result = require('child_process').spawnSync(p, ['--version'], { encoding: 'utf8', timeout: 5000 });
            if (result.status === 0) {
                return p;
            }
        } catch (e) {
            continue;
        }
    }
    
    return 'python';
}

async function startListening(window) {
    if (isListening) {
        console.log('[KWS] 已经在监听中');
        return;
    }

    mainWindow = window;

    if (!fs.existsSync(KWS_SCRIPT)) {
        console.error('[KWS] Python 脚本不存在:', KWS_SCRIPT);
        return;
    }

    const pythonPath = getPythonPath();
    console.log('[KWS] 使用 Python:', pythonPath);

    try {
        kwsProcess = spawn(pythonPath, [KWS_SCRIPT], {
            cwd: MODELS_DIR,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        });

        kwsProcess.stdout.on('data', (data) => {
            const lines = data.toString().trim().split('\n');
            for (const line of lines) {
                try {
                    const msg = JSON.parse(line);
                    console.log('[KWS]', msg.status, msg.message || msg.keyword || '');
                    
                    if (msg.status === 'ready') {
                        isListening = true;
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('wake-word-listening', true);
                        }
                    } else if (msg.status === 'detected') {
                        console.log('[KWS] 检测到唤醒词:', msg.keyword);
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            console.log('[KWS] 发送事件到 petWindow, id:', mainWindow.id);
                            mainWindow.webContents.send('wake-word-detected', msg.keyword);
                        } else {
                            console.log('[KWS] mainWindow 不可用, destroyed:', mainWindow ? mainWindow.isDestroyed() : 'null');
                        }
                    } else if (msg.status === 'error') {
                        console.error('[KWS] 错误:', msg.message);
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('wake-word-error', msg.message);
                        }
                    }
                } catch (e) {
                    console.log('[KWS] stdout:', line);
                }
            }
        });

        kwsProcess.stderr.on('data', (data) => {
            console.error('[KWS] stderr:', data.toString());
        });

        kwsProcess.on('error', (err) => {
            console.error('[KWS] 进程错误:', err);
            isListening = false;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('wake-word-error', err.message);
            }
        });

        kwsProcess.on('close', (code) => {
            console.log('[KWS] 进程退出:', code);
            isListening = false;
            kwsProcess = null;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('wake-word-listening', false);
            }
        });

    } catch (e) {
        console.error('[KWS] 启动失败:', e);
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('wake-word-error', e.message);
        }
    }
}

function stopListening() {
    return new Promise((resolve) => {
        if (!isListening || !kwsProcess) {
            console.log('[KWS] 未在监听');
            resolve();
            return;
        }

        const pid = kwsProcess.pid;
        let resolved = false;

        const doResolve = () => {
            if (resolved) return;
            resolved = true;
            isListening = false;
            kwsProcess = null;
            console.log('[KWS] 停止监听');
            
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('wake-word-listening', false);
            }
            resolve();
        };

        kwsProcess.on('close', () => {
            console.log('[KWS] 进程已退出');
            doResolve();
        });

        try {
            console.log('[KWS] 发送停止信号...');
            process.kill(pid, 'SIGTERM');
            
            setTimeout(() => {
                try {
                    process.kill(pid, 0);
                    console.log('[KWS] 进程仍在运行，发送 SIGKILL');
                    process.kill(pid, 'SIGKILL');
                } catch (e) {
                    // 进程已退出
                }
            }, 1000);

            setTimeout(() => {
                console.log('[KWS] 超时，强制完成停止');
                doResolve();
            }, 3000);
            
        } catch (e) {
            console.error('[KWS] 停止失败:', e);
            doResolve();
        }
    });
}

function setupIpcHandlers() {
    ipcMain.handle('kws-start', async (event) => {
        const win = require('electron').BrowserWindow.fromWebContents(event.sender);
        await startListening(win);
        return { success: true, listening: isListening };
    });

    ipcMain.handle('kws-stop', async () => {
        await stopListening();
        return { success: true, listening: false };
    });

    ipcMain.handle('kws-status', async () => {
        return { 
            success: true, 
            listening: isListening,
            modelLoaded: true
        };
    });

    ipcMain.handle('kws-update-keywords', async () => {
        return { success: true };
    });
}

module.exports = {
    startListening,
    stopListening,
    setupIpcHandlers,
};
