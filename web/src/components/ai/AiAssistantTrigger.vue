<template>
  <div class="ai-trigger-wrap">
    <button class="header-icon-button" type="button" aria-label="打开助手" @click="session.toggle()">
      <TheIcon icon="mdi:chat-processing-outline" :size="18" />
    </button>
    <AiAssistantDrawer />
  </div>
</template>

<script setup>
import TheIcon from '@/components/icon/TheIcon.vue'
import AiAssistantDrawer from '@/components/ai/AiAssistantDrawer.vue'
import { useAiSession } from '@/composables/useAiSession'

const session = useAiSession()
</script>

<style scoped>
.ai-trigger-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
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
