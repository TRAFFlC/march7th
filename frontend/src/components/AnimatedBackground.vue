<template>
  <div class="animated-background">
    <div class="bg-base"></div>
    <div class="bg-scroll" :style="{ animationDuration: animationDuration }">
      <div 
        v-for="(item, index) in allItems" 
        :key="index"
        class="scroll-item"
        :style="item.style"
      ></div>
    </div>
    <div class="bg-overlay"></div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const baseImages = ref([])
const isLoggedIn = ref(false)
let checkInterval = null

const animationDuration = computed(() => {
  return isLoggedIn.value ? '240s' : '60s'
})

function checkLoginStatus() {
  const token = localStorage.getItem('token')
  isLoggedIn.value = !!token
}

async function loadBackgrounds() {
  try {
    console.log('[Background] 开始加载背景图片...')
    const response = await fetch('http://127.0.0.1:8000/api/system/backgrounds')
    const data = await response.json()
    console.log('[Background] API 返回:', data)
    if (data.success && data.images.length > 0) {
      console.log(`[Background] 获取到 ${data.images.length} 张图片`)
      baseImages.value = data.images
    } else {
      console.warn('[Background] 未获取到图片或请求失败')
    }
  } catch (e) {
    console.error('[Background] 加载失败:', e)
  }
}

const allItems = computed(() => {
  if (baseImages.value.length === 0) return []
  
  const items = []
  const imgW = 180
  const imgH = 250
  const angle = -30
  
  const rad = Math.abs(angle) * Math.PI / 180
  const cosA = Math.cos(rad)
  const sinA = Math.sin(rad)
  
  const boundW = imgW * cosA + imgH * sinA
  const boundH = imgW * sinA + imgH * cosA
  
  const overlapX = boundW * 0.15
  const overlapY = boundH * 0.15
  
  const stepX = boundW - overlapX
  const stepY = boundH - overlapY
  
  const cols = 15
  const rows = 12
  
  for (let row = -3; row < rows + 3; row++) {
    for (let col = -3; col < cols + 3; col++) {
      const imgIndex = Math.abs((row * cols + col)) % baseImages.value.length
      const img = baseImages.value[imgIndex]
      
      const offsetX = (row % 2) * (stepX / 2)
      const x = col * stepX + offsetX
      const y = row * stepY
      
      items.push({
        style: {
          backgroundImage: `url(http://127.0.0.1:8000${img})`,
          width: `${imgW}px`,
          height: `${imgH}px`,
          left: `${x}px`,
          top: `${y}px`,
          transform: `rotate(${angle}deg)`,
        }
      })
    }
  }
  
  return items
})

onMounted(() => {
  loadBackgrounds()
  checkLoginStatus()
  checkInterval = setInterval(checkLoginStatus, 1000)
})

onUnmounted(() => {
  if (checkInterval) {
    clearInterval(checkInterval)
  }
})
</script>

<style scoped>
.animated-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  z-index: -1;
  overflow: hidden;
  pointer-events: none;
}

.bg-base {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(135deg, #1a1a3e 0%, #2d1b4e 50%, #1a1a3e 100%);
}

.bg-scroll {
  position: absolute;
  width: 300%;
  height: 300%;
  top: -100%;
  left: -100%;
  animation: diagonalScroll 120s linear infinite;
}

@keyframes diagonalScroll {
  0% {
    transform: translate(0, 0);
  }
  100% {
    transform: translate(33.33%, 33.33%);
  }
}

.scroll-item {
  position: absolute;
  background-size: cover;
  background-position: center;
  border-radius: 4px;
  opacity: 0.4;
  filter: blur(0.5px) saturate(1.2);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.bg-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    135deg,
    rgba(30, 20, 60, 0.45) 0%,
    rgba(50, 30, 80, 0.3) 50%,
    rgba(30, 20, 60, 0.45) 100%
  );
}
</style>
