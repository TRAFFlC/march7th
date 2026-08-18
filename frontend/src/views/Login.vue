<template>
  <div class="login-page">
    <div class="login-container">
      <div class="login-header">
        <div class="logo">✨</div>
        <h1>七音盒Music7ox</h1>
        <p>与虚拟角色开启语音对话</p>
      </div>

      <div class="login-tabs">
        <button 
          :class="['tab-btn', { active: mode === 'login' }]"
          @click="mode = 'login'"
        >
          登录
        </button>
        <button 
          :class="['tab-btn', { active: mode === 'register' }]"
          @click="mode = 'register'"
        >
          注册
        </button>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <div class="form-group">
          <label>用户名</label>
          <input 
            v-model="username"
            type="text" 
            class="input-field"
            placeholder="请输入用户名"
            autocomplete="username"
          />
        </div>

        <div class="form-group">
          <label>密码</label>
          <input 
            v-model="password"
            type="password" 
            class="input-field"
            placeholder="请输入密码"
            :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          />
        </div>

        <div v-if="mode === 'register'" class="form-group">
          <label>确认密码</label>
          <input 
            v-model="confirmPassword"
            type="password" 
            class="input-field"
            placeholder="请再次输入密码"
            autocomplete="new-password"
          />
        </div>

        <p v-if="error" class="error-message">{{ error }}</p>

        <button 
          type="submit" 
          class="btn btn-primary submit-btn"
          :disabled="loading"
        >
          <span v-if="loading" class="loading-spinner"></span>
          <span v-else>{{ mode === 'login' ? '登录' : '注册' }}</span>
        </button>
      </form>

      <div class="login-footer">
        <p>默认管理员账号: admin / admin123</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const mode = ref('login')
const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function handleSubmit() {
  error.value = ''
  
  if (!username.value.trim()) {
    error.value = '请输入用户名'
    return
  }
  
  if (!password.value) {
    error.value = '请输入密码'
    return
  }
  
  if (mode.value === 'register') {
    if (password.value.length < 6) {
      error.value = '密码至少6个字符'
      return
    }
    if (password.value !== confirmPassword.value) {
      error.value = '两次输入的密码不一致'
      return
    }
  }
  
  loading.value = true
  
  try {
    if (mode.value === 'login') {
      await authStore.login(username.value.trim(), password.value)
    } else {
      await authStore.register(username.value.trim(), password.value)
    }
    router.push('/')
  } catch (err) {
    error.value = err.detail || '操作失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.login-container {
  width: 100%;
  max-width: 420px;
  padding: 40px;
  background: rgba(26, 26, 46, 0.95);
  border: 1px solid var(--border-color);
  border-radius: 20px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.5);
}

.login-header {
  text-align: center;
  margin-bottom: 30px;
}

.logo {
  font-size: 64px;
  margin-bottom: 16px;
}

.login-header h1 {
  color: var(--accent-secondary);
  font-size: 28px;
  margin-bottom: 8px;
}

.login-header p {
  color: var(--text-secondary);
  font-size: 16px;
}

.login-tabs {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
}

.tab-btn {
  flex: 1;
  padding: 14px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid var(--border-color);
  border-radius: 10px;
  color: var(--text-secondary);
  font-size: 16px;
  font-weight: 500;
}

.tab-btn:hover {
  background: rgba(255, 255, 255, 0.1);
}

.tab-btn.active {
  background: linear-gradient(135deg, rgba(233, 69, 96, 0.3) 0%, rgba(255, 107, 157, 0.2) 100%);
  border-color: var(--accent-primary);
  color: var(--accent-secondary);
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.form-group label {
  color: var(--accent-secondary);
  font-size: 14px;
  font-weight: 500;
}

.error-message {
  color: #ff6b6b;
  font-size: 14px;
  text-align: center;
  padding: 10px;
  background: rgba(255, 82, 82, 0.1);
  border-radius: 8px;
}

.submit-btn {
  width: 100%;
  padding: 16px;
  font-size: 18px;
  margin-top: 10px;
}

.login-footer {
  margin-top: 24px;
  text-align: center;
}

.login-footer p {
  color: var(--text-secondary);
  font-size: 13px;
}
</style>
