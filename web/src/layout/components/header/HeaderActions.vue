<template>
  <div class="header-actions" aria-label="页面工具">
    <div class="header-action header-action--ai">
      <AiAssistantTrigger />
    </div>
    <div class="header-action header-action--notification">
      <NotificationBell />
    </div>
    <div class="header-action header-action--language">
      <Languages />
    </div>
    <div class="header-action header-action--theme">
      <ThemeMode />
    </div>
    <div class="header-action header-action--fullscreen">
      <FullScreen />
    </div>
    <div class="header-action header-action--avatar">
      <UserAvatar :profile-path="props.profilePath" />
    </div>
  </div>
</template>

<script setup>
import AiAssistantTrigger from '@/components/ai/AiAssistantTrigger.vue'
import FullScreen from './components/FullScreen.vue'
import Languages from './components/Languages.vue'
import NotificationBell from './components/NotificationBell.vue'
import ThemeMode from './components/ThemeMode.vue'
import UserAvatar from './components/UserAvatar.vue'

const props = defineProps({
  profilePath: {
    type: String,
    default: '/profile',
  },
})
</script>

<style scoped>
.header-actions {
  display: flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: flex-end;
  gap: 2px;
  min-width: 0;
  color: inherit;
}

.header-action {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  min-width: 40px;
  min-height: 40px;
  line-height: 1;
}

.header-action--avatar {
  min-width: auto;
  padding-left: 4px;
}

.header-action :deep(.n-icon) {
  margin-right: 0 !important;
  color: inherit;
}

@media (max-width: 767.98px) {
  .header-action--language,
  .header-action--fullscreen {
    display: none;
  }

  .header-action--avatar {
    padding-left: 0;
  }
}

@media (max-width: 479.98px) {
  .header-actions {
    gap: 0;
  }
}
</style>
