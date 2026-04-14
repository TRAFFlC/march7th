import axios from 'axios'

const API_BASE = '/api'

const api = axios.create({
  baseURL: API_BASE,
  timeout: 120000,
})

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      try {
        const response = await axios.post(API_BASE + '/auth/auto-login')
        if (response.data?.success) {
          localStorage.setItem('token', response.data.token)
          localStorage.setItem('user', JSON.stringify(response.data.user))
          error.config.headers.Authorization = `Bearer ${response.data.token}`
          return axios(error.config)
        }
      } catch (e) {
        console.error('Auto login retry failed:', e)
      }
    }
    const errorData = error.response?.data || { detail: error.message || '网络错误' }
    return Promise.reject(errorData)
  }
)

export default {
  get: (url, params) => api.get(url, { params }),
  post: (url, data) => api.post(url, data),
  put: (url, data) => api.put(url, data),
  delete: (url) => api.delete(url),
}
