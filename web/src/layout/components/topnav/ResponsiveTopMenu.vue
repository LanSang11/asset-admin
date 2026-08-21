<template>
  <div class="responsive-top-menu">
    <div class="responsive-top-menu__desktop">
      <n-menu
        mode="horizontal"
        responsive
        inverted
        :options="menuOptions"
        :value="props.activeKey"
        @update:value="handleSelect"
      />
    </div>

    <div class="responsive-top-menu__mobile">
      <n-button
        class="responsive-top-menu__trigger mobile-menu-trigger"
        quaternary
        circle
        aria-label="打开导航菜单"
        @click="drawerOpen = true"
      >
        <template #icon>
          <n-icon size="22"><icon-mdi:menu /></n-icon>
        </template>
      </n-button>
    </div>

    <n-drawer v-model:show="drawerOpen" placement="left" width="min(360px, calc(100vw - 24px))">
      <n-drawer-content title="功能导航" closable>
        <nav aria-label="移动端功能导航">
          <n-menu
            class="responsive-top-menu__drawer-menu"
            accordion
            :indent="20"
            :options="menuOptions"
            :value="props.activeKey"
            @update:value="handleSelect"
          />
        </nav>
      </n-drawer-content>
    </n-drawer>
  </div>
</template>

<script setup>
import { renderCustomIcon, renderIcon } from '@/utils'

const props = defineProps({
  menuModels: {
    type: Array,
    default: () => [],
  },
  activeKey: {
    type: [String, Number],
    default: null,
  },
})

const emit = defineEmits(['select'])
const route = useRoute()
const drawerOpen = ref(false)

function decorateMenuModel(model) {
  const menuItem = { ...model }
  if (!menuItem.icon && menuItem.customIcon) {
    menuItem.icon = renderCustomIcon(menuItem.customIcon, { size: 20, class: 'app-nav-icon' })
  } else if (!menuItem.icon && menuItem.iconName) {
    menuItem.icon = renderIcon(menuItem.iconName, { size: 20, class: 'app-nav-icon' })
  }
  if (menuItem.children?.length) {
    menuItem.children = menuItem.children.map(decorateMenuModel)
  }
  return menuItem
}

const menuOptions = computed(() => props.menuModels.map(decorateMenuModel))

function handleSelect(key, model) {
  drawerOpen.value = false
  emit('select', key, model)
}

watch(
  () => route.fullPath,
  () => {
    drawerOpen.value = false
  }
)
</script>

<style scoped>
.responsive-top-menu,
.responsive-top-menu__desktop,
.responsive-top-menu__desktop :deep(.n-menu) {
  width: 100%;
  min-width: 0;
}

.responsive-top-menu {
  display: flex;
  align-items: center;
}

.responsive-top-menu__desktop {
  display: flex;
  align-items: center;
  overflow: hidden;
}

.responsive-top-menu__desktop :deep(.n-menu-item-content) {
  min-height: 48px;
  padding: 0 14px;
  border-radius: 8px;
}

.responsive-top-menu__desktop :deep(.n-menu-item-content-header) {
  font-size: 14px;
  white-space: nowrap;
}

.responsive-top-menu__desktop :deep(.n-menu-item-content__icon) {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  line-height: 1;
}

.responsive-top-menu__mobile {
  display: none;
}

.responsive-top-menu__trigger {
  width: 40px;
  height: 40px;
  color: #d7e4f2;
}

@media (max-width: 1199.98px) {
  .responsive-top-menu__desktop {
    display: none;
  }

  .responsive-top-menu__mobile {
    display: flex;
    align-items: center;
  }
}
</style>
