<script setup>
import { useAppStore } from '@/store'
import { useDark, useToggle } from '@vueuse/core'

const appStore = useAppStore()
const isDark = useDark()
const toggleDark = () => {
  appStore.toggleDark()
  useToggle(isDark)()
}
</script>

<template>
  <button
    class="header-icon-button"
    type="button"
    :aria-label="isDark ? '切换浅色模式' : '切换深色模式'"
    @click="toggleDark"
  >
    <n-icon size="18">
      <icon-mdi-moon-waning-crescent v-if="isDark" />
      <icon-mdi-white-balance-sunny v-else />
    </n-icon>
  </button>
</template>

<style scoped>
.header-icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  min-height: 40px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  color: inherit;
  background: transparent;
  line-height: 1;
  cursor: pointer;
}

.header-icon-button:hover,
.header-icon-button:focus-visible {
  background: var(--topbar-action-hover, rgba(148, 163, 184, 0.18));
  outline: none;
}

.header-icon-button:focus-visible {
  box-shadow: 0 0 0 2px var(--shell-accent);
}
</style>
