import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: { requiresAuth: false }
  },
  {
    path: '/',
    name: 'Main',
    component: () => import('../views/Main.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Chat',
        component: () => import('../views/Chat.vue')
      },
      {
        path: 'llm',
        name: 'LLM',
        component: () => import('../views/LLM.vue')
      },
      {
        path: 'tts',
        name: 'TTS',
        component: () => import('../views/TTS.vue')
      },
      {
        path: 'rag',
        name: 'RAG',
        component: () => import('../views/RAG.vue')
      },
      {
        path: 'characters',
        name: 'Characters',
        component: () => import('../views/Characters.vue')
      },
      {
        path: 'personal',
        name: 'Personal',
        component: () => import('../views/Personal.vue')
      },
      {
        path: 'admin',
        name: 'Admin',
        component: () => import('../views/Admin.vue'),
        meta: { requiresAdmin: true }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  
  if (to.meta.requiresAuth && !authStore.isLoggedIn) {
    next('/login')
  } else if (to.meta.requiresAdmin && authStore.user?.role !== 'admin') {
    next('/')
  } else if (to.path === '/login' && authStore.isLoggedIn) {
    next('/')
  } else {
    next()
  }
})

export default router
