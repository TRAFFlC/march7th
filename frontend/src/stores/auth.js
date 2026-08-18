import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../utils/api'

function readStoredUser() {
  try {
    return JSON.parse(localStorage.getItem('user') || 'null')
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || null)
  const user = ref(readStoredUser())

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(username, password) {
    const response = await api.post('/auth/login', { username, password })
    if (response.success) {
      token.value = response.token
      user.value = response.user
      localStorage.setItem('token', response.token)
      localStorage.setItem('user', JSON.stringify(response.user))
      try {
        await api.post('/auth/share-token')
      } catch (e) {}
    }
    return response
  }

  async function register(username, password) {
    const response = await api.post('/auth/register', { username, password })
    if (response.success) {
      token.value = response.token
      user.value = response.user
      localStorage.setItem('token', response.token)
      localStorage.setItem('user', JSON.stringify(response.user))
      try {
        await api.post('/auth/share-token')
      } catch (e) {}
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
    isAdmin,
    login,
    register,
    logout,
    fetchUser
  }
})
