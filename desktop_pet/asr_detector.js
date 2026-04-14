/**
 * Sherpa-ONNX 离线语音识别模块
 * 使用 Python 子进程实现语音识别
 */

const { ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

let asrProcess = null;
let isListening = false;
let mainWindow = null;

const MODELS_DIR = path.resolve(__dirname, 'models');
const ASR_SCRIPT = path.join(MODELS_DIR, 'asr_service.py');

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
        console.log('[ASR] 已经在监听中');
        return;
    }

    mainWindow = window;

    if (!fs.existsSync(ASR_SCRIPT)) {
        console.error('[ASR] Python 脚本不存在:', ASR_SCRIPT);
        return;
    }

    const pythonPath = getPythonPath();
    console.log('[ASR] 使用 Python:', pythonPath);

    try {
        asrProcess = spawn(pythonPath, [ASR_SCRIPT], {
            cwd: MODELS_DIR,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
        });

        asrProcess.stdout.on('data', (data) => {
            const lines = data.toString().trim().split('\n');
            for (const line of lines) {
                try {
                    const msg = JSON.parse(line);
                    console.log('[ASR]', msg.status, msg.text || msg.message || '');
                    
                    if (msg.status === 'ready') {
                        isListening = true;
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('asr-ready', true);
                        }
                    } else if (msg.status === 'listening') {
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('asr-listening', true);
                        }
                    } else if (msg.status === 'partial') {
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('asr-partial', msg.text);
                        }
                    } else if (msg.status === 'final') {
                        console.log('[ASR] 最终识别结果:', msg.text);
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('asr-result', msg.text);
                        }
                    } else if (msg.status === 'error') {
                        console.error('[ASR] 错误:', msg.message);
                        if (mainWindow && !mainWindow.isDestroyed()) {
                            mainWindow.webContents.send('asr-error', msg.message);
                        }
                    }
                } catch (e) {
                    console.log('[ASR] stdout:', line);
                }
            }
        });

        asrProcess.stderr.on('data', (data) => {
            console.error('[ASR] stderr:', data.toString());
        });

        asrProcess.on('error', (err) => {
            console.error('[ASR] 进程错误:', err);
            isListening = false;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('asr-error', err.message);
            }
        });

        asrProcess.on('close', (code) => {
            console.log('[ASR] 进程退出:', code);
            isListening = false;
            asrProcess = null;
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('asr-listening', false);
            }
        });

    } catch (e) {
        console.error('[ASR] 启动失败:', e);
        if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('asr-error', e.message);
        }
    }
}

function stopListening() {
    return new Promise((resolve) => {
        if (!isListening || !asrProcess) {
            console.log('[ASR] 未在监听');
            resolve();
            return;
        }

        const pid = asrProcess.pid;
        let resolved = false;

        const doResolve = () => {
            if (resolved) return;
            resolved = true;
            isListening = false;
            asrProcess = null;
            console.log('[ASR] 停止监听');
            
            if (mainWindow && !mainWindow.isDestroyed()) {
                mainWindow.webContents.send('asr-listening', false);
            }
            resolve();
        };

        asrProcess.on('close', () => {
            console.log('[ASR] 进程已退出');
            doResolve();
        });

        try {
            console.log('[ASR] 发送停止信号...');
            process.kill(pid, 'SIGTERM');
            
            setTimeout(() => {
                try {
                    process.kill(pid, 0);
                    console.log('[ASR] 进程仍在运行，发送 SIGKILL');
                    process.kill(pid, 'SIGKILL');
                } catch (e) {
                    // 进程已退出
                }
            }, 1000);

            setTimeout(() => {
                console.log('[ASR] 超时，强制完成停止');
                doResolve();
            }, 3000);
            
        } catch (e) {
            console.error('[ASR] 停止失败:', e);
            doResolve();
        }
    });
}

function setupIpcHandlers() {
    ipcMain.handle('asr-start', async (event) => {
        const win = require('electron').BrowserWindow.fromWebContents(event.sender);
        await startListening(win);
        return { success: true, listening: isListening };
    });

    ipcMain.handle('asr-stop', async () => {
        await stopListening();
        return { success: true, listening: false };
    });

    ipcMain.handle('asr-status', async () => {
        return { 
            success: true, 
            listening: isListening
        };
    });
}

module.exports = {
    startListening,
    stopListening,
    setupIpcHandlers,
};
