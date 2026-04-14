import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../utils/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user = ref(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  async function autoLogin() {
    try {
      const response = await api.post('/auth/auto-login')
      if (response.success) {
        token.value = response.token
        user.value = response.user
        localStorage.setItem('token', response.token)
        localStorage.setItem('user', JSON.stringify(response.user))
        try { await api.post('/auth/share-token') } catch (e) {}
      }
    } catch (e) {
      console.error('Auto login failed:', e)
    }
  }

  async function login(username, password) {
    const response = await api.post('/auth/login', { username, password })
    if (response.success) {
      token.value = response.token
      user.value = response.user
      localStorage.setItem('token', response.token)
      localStorage.setItem('user', JSON.stringify(response.user))
      try { await api.post('/auth/share-token') } catch (e) {}
    }
    return response
  }

  async function logout() {
    try {
      await api.delete('/auth/shared-token')
    } catch (e) {}
    token.value = null
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function fetchUser() {
    if (!token.value) return null
    try {
      const response = await api.get('/auth/me')
      if (response.success) {
        user.value = response.user
        localStorage.setItem('user', JSON.stringify(response.user))
      }
      return response.user
    } catch {
      logout()
      return null
    }
  }

  return {
    token,
    user,
    isLoggedIn,
    autoLogin,
    login,
    logout,
    fetchUser
  }
})
