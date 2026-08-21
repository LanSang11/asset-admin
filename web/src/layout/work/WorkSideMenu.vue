<template>
  <n-menu
    ref="menu"
    class="side-menu"
    accordion
    :indent="18"
    :collapsed-icon-size="22"
    :collapsed-width="64"
    :options="menuOptions"
    :value="activeKey"
    @update:value="handleMenuSelect"
  />
</template>

<script setup>
import { usePermissionStore, useAppStore } from '@/store'
import { renderCustomIcon, renderIcon } from '@/utils'
import {
  buildWorkMenuModels,
  getActiveMenuKey,
  navigateMenuModel,
} from '@/layout/navigation/menu-model'

const router = useRouter()
const curRoute = useRoute()
const permissionStore = usePermissionStore()
const appStore = useAppStore()

const activeKey = computed(() => getActiveMenuKey(curRoute))

/** 工作台固定菜单（方案 A）；领用/资产/审批/看板/AI 按 API 显隐 */
const menuOptions = computed(() => {
  return buildWorkMenuModels(permissionStore.accessApis).map(decorateMenuIcon)
})

function decorateMenuIcon(model) {
  const option = {
    ...model,
    icon: renderMenuIcon(model),
  }
  if (model.children) option.children = model.children.map(decorateMenuIcon)
  return option
}

function renderMenuIcon(model) {
  if (model.customIcon) return renderCustomIcon(model.customIcon, { size: 18 })
  if (model.iconName) return renderIcon(model.iconName, { size: 18 })
  return null
}

const menu = ref(null)
watch(curRoute, async () => {
  await nextTick()
  menu.value?.showOption()
})

async function handleMenuSelect(key, item) {
  await navigateMenuModel(item, {
    router,
    route: curRoute,
    reloadPage: () => appStore.reloadPage(),
  })
}
</script>

<style lang="scss">
.side-menu:not(.n-menu--collapsed) {
  .n-menu-item-content {
    &::before {
      left: 5px;
      right: 5px;
    }
    &.n-menu-item-content--selected,
    &:hover {
      &::before {
        border-left: 4px solid var(--primary-color);
      }
    }
  }
}
</style>
