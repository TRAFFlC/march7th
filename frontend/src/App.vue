<template>
  <div class="app-container">
    <AnimatedBackground />
    <router-view />
  </div>
</template>

<script setup>
import AnimatedBackground from './components/AnimatedBackground.vue'
</script>

<style>
.app-container {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
}
</style>
