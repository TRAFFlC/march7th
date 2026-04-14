import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/',
    name: 'Main',
    component: () => import('../views/Main.vue'),
    meta: { requiresAuth: true },
    children: [
      { path: '', name: 'Chat', component: () => import('../views/Chat.vue') },
      { path: 'llm', name: 'LLM', component: () => import('../views/LLM.vue') },
      { path: 'tts', name: 'TTS', component: () => import('../views/TTS.vue') },
      { path: 'rag', name: 'RAG', component: () => import('../views/RAG.vue') },
      { path: 'characters', name: 'Characters', component: () => import('../views/Characters.vue') },
      { path: 'personal', name: 'Personal', component: () => import('../views/Personal.vue') },
      { path: 'settings', name: 'Settings', component: () => import('../views/Settings.vue') },
      { path: 'debug', name: 'Debug', component: () => import('../views/Debug.vue') },
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to, from, next) => {
  const authStore = useAuthStore()
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    await authStore.autoLogin()
    if (authStore.isLoggedIn) {
      next()
    } else {
      next()
    }
  } else {
    next()
  }
})

export default router
