<template>
  <n-layout class="portal-layout" wh-full>
    <PortalTopBar
      :menu-models="menuModels"
      :active-key="activeKey"
      portal="work"
      profile-path="/work/profile"
      @select="handleMenuSelect"
    />
    <section class="portal-main">
      <AppMain />
    </section>
  </n-layout>
</template>

<script setup>
/**
 * 方案 B：员工/主管工作台壳；菜单继续只由工作台 API 权限生成。
 */
import AppMain from '@/layout/components/AppMain.vue'
import PortalTopBar from '@/layout/components/topnav/PortalTopBar.vue'
import {
  buildWorkMenuModels,
  getActiveMenuKey,
  navigateMenuModel,
} from '@/layout/navigation/menu-model.js'
import { useAppStore, usePermissionStore } from '@/store'

const appStore = useAppStore()
const permissionStore = usePermissionStore()
const router = useRouter()
const route = useRoute()

const menuModels = computed(() => buildWorkMenuModels(permissionStore.accessApis || []))
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

.portal-main {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  background: var(--shell-bg, #eef3f8);
}
</style>
