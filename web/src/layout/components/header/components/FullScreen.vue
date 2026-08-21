<template>
  <button
    v-if="appStore.fullScreen"
    class="fullscreen-action"
    type="button"
    :aria-label="isFullscreen ? '退出全屏' : '进入全屏'"
    @click="toggle"
  >
    <n-icon size="18">
      <icon-ant-design:fullscreen-exit-outlined v-if="isFullscreen" />
      <icon-ant-design:fullscreen-outlined v-else />
    </n-icon>
  </button>
</template>

<script setup>
import { useFullscreen } from '@vueuse/core'
import { useAppStore } from '@/store'

const appStore = useAppStore()
const { isFullscreen, toggle } = useFullscreen()
</script>

<style scoped>
.fullscreen-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  color: inherit;
  line-height: 1;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 8px;
}

.fullscreen-action:hover,
.fullscreen-action:focus-visible {
  background: var(--topbar-action-hover, rgba(148, 163, 184, 0.18));
  outline: none;
}

.fullscreen-action:focus-visible {
  box-shadow: 0 0 0 2px var(--primary-color, #2080f0);
}

@media (max-width: 767.98px) {
  .fullscreen-action {
    display: none;
  }
}
</style>
