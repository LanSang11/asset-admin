<template>
  <AppPage :show-footer="showFooter">
    <header v-if="showHeader" class="common-page__header" flex items-center justify-between>
      <slot v-if="$slots.header" name="header" />
      <template v-else>
        <h2 class="common-page__title">{{ title || route.meta?.title }}</h2>
        <slot name="action" />
      </template>
    </header>

    <n-card class="common-page__surface" flex-1 :bordered="false">
      <slot />
    </n-card>
  </AppPage>
</template>

<script setup>
defineProps({
  showFooter: {
    type: Boolean,
    default: false,
  },
  showHeader: {
    type: Boolean,
    default: true,
  },
  title: {
    type: String,
    default: undefined,
  },
})
const route = useRoute()
</script>
