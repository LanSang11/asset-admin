<template>
  <router-link class="side-logo" :class="{ collapsed: appStore.collapsed }" to="/">
    <!-- 系统标识：圆形，固定盒模型防止撑破侧栏 -->
    <img class="side-logo__img" :src="logoUrl" alt="系统标识" draggable="false" />
    <h2 v-show="!appStore.collapsed" class="side-logo__title">
      {{ title }}
    </h2>
  </router-link>
</template>

<script setup>
import { useAppStore } from '@/store'

const title = import.meta.env.VITE_TITLE || '资产管理系统'
const appStore = useAppStore()
// public 资源，构建后路径稳定，不依赖 iconify/svg 占位
const logoUrl = `${import.meta.env.BASE_URL}resource/company-logo.jpg`
</script>

<style scoped>
.side-logo {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  height: 60px;
  padding: 0 12px;
  box-sizing: border-box;
  overflow: hidden;
  text-decoration: none;
  flex-shrink: 0;
}

.side-logo.collapsed {
  justify-content: center;
  padding: 0 8px;
}

.side-logo__img {
  width: 36px;
  height: 36px;
  min-width: 36px;
  min-height: 36px;
  max-width: 36px;
  max-height: 36px;
  border-radius: 50%;
  object-fit: cover;
  object-position: center;
  flex-shrink: 0;
  display: block;
  /* 轻微描边，浅/深色都压得住 */
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.06);
  background: #fff;
}

.side-logo.collapsed .side-logo__img {
  width: 32px;
  height: 32px;
  min-width: 32px;
  min-height: 32px;
  max-width: 32px;
  max-height: 32px;
}

.side-logo__title {
  margin: 0 0 0 10px;
  max-width: 140px;
  flex-shrink: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 15px;
  font-weight: 700;
  line-height: 1.2;
  color: var(--primary-color, #2080f0);
}
</style>
