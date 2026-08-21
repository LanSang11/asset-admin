<template>
  <header class="portal-topbar" :data-portal="props.portal">
    <div class="portal-topbar__inner">
      <TopBrand class="portal-topbar__brand" :portal="props.portal" />
      <div class="portal-topbar__nav">
        <ResponsiveTopMenu
          :menu-models="props.menuModels"
          :active-key="props.activeKey"
          @select="forwardSelect"
        />
      </div>
      <HeaderActions class="portal-topbar__actions" :profile-path="props.profilePath" />
    </div>
  </header>
</template>

<script setup>
import HeaderActions from '@/layout/components/header/HeaderActions.vue'
import ResponsiveTopMenu from './ResponsiveTopMenu.vue'
import TopBrand from './TopBrand.vue'

const props = defineProps({
  menuModels: {
    type: Array,
    default: () => [],
  },
  activeKey: {
    type: [String, Number],
    default: null,
  },
  portal: {
    type: String,
    required: true,
    validator: (value) => ['admin', 'work'].includes(value),
  },
  profilePath: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['select'])

function forwardSelect(key, model) {
  emit('select', key, model)
}
</script>

<style scoped>
.portal-topbar {
  position: relative;
  z-index: 20;
  display: flex;
  flex: 0 0 72px;
  align-items: center;
  width: 100%;
  height: 72px;
  color: var(--shell-header-text, #fff);
  background: var(--shell-header-bg, #071a31);
  border-bottom: 1px solid rgba(148, 163, 184, 0.18);
  box-sizing: border-box;
}

.portal-topbar__inner {
  display: flex;
  align-items: center;
  gap: 16px;
  width: 100%;
  min-width: 0;
  height: 100%;
  padding: 0 24px;
  box-sizing: border-box;
}

.portal-topbar__nav {
  display: flex;
  flex: 1 1 auto;
  align-items: center;
  width: 100%;
  min-width: 0;
}

@media (max-width: 1199.98px) {
  .portal-topbar__inner {
    gap: 8px;
    padding: 0 18px;
  }
}

@media (max-width: 767.98px) {
  .portal-topbar {
    flex-basis: 64px;
    height: 64px;
  }

  .portal-topbar__inner {
    padding: 0 12px;
  }
}

@media (max-width: 479.98px) {
  .portal-topbar__inner {
    gap: 4px;
    padding: 0 8px;
  }
}
</style>
