<template>
  <n-layout class="portal-layout" wh-full>
    <PortalTopBar
      :menu-models="menuModels"
      :active-key="activeKey"
      portal="admin"
      profile-path="/profile"
      @select="handleMenuSelect"
    />
    <AcceptanceModeBanner />
    <section v-if="tags.visible" class="portal-routebar" dark="border-0">
      <AppTags :style="{ height: 'var(--shell-routebar-height, 48px)' }" />
    </section>
    <section class="portal-main">
      <AppMain />
    </section>
  </n-layout>
</template>

<script setup>
import AppMain from './components/AppMain.vue'
import AppTags from './components/tags/index.vue'
import AcceptanceModeBanner from './components/AcceptanceModeBanner.vue'
import PortalTopBar from './components/topnav/PortalTopBar.vue'
import {
  buildAdminMenuModels,
  getActiveMenuKey,
  navigateMenuModel,
} from './navigation/menu-model.js'
import { useAppStore, usePermissionStore } from '@/store'
import { tags } from '~/settings'

const appStore = useAppStore()
const permissionStore = usePermissionStore()
const router = useRouter()
const route = useRoute()

const menuModels = computed(() => buildAdminMenuModels(permissionStore.menus || []))
const activeKey = computed(() => getActiveMenuKey(route))

function handleMenuSelect(key, model) {
  if (key == null || !model) return
  return navigateMenuModel(model, {
    router,
    route,
    reloadPage: () => appStore.reloadPage(),
  })
}
</script>

<style scoped>
.portal-layout {
  display: flex;
  flex-direction: column;
  min-width: 0;
  overflow: hidden;
}

.portal-routebar {
  display: block;
  flex: 0 0 auto;
  overflow: hidden;
  background: var(--shell-surface, #fff);
  border-bottom: 1px solid var(--shell-border, #e5e7eb);
}

.portal-main {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  background: var(--shell-bg, #eef3f8);
}

@media (max-width: 767.98px) {
  .portal-routebar {
    display: none;
  }
}
</style>
