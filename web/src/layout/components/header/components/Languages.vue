<template>
  <n-dropdown :options="options" @select="handleChangeLocale">
    <button class="header-icon-button" type="button" aria-label="切换语言">
      <n-icon size="18"><icon-mdi:globe /></n-icon>
    </button>
  </n-dropdown>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/store'
import { router } from '~/src/router'

const store = useAppStore()
const { availableLocales, t } = useI18n()

const options = computed(() => {
  let select = []
  availableLocales.forEach((locale) => {
    select.push({
      label: t('lang', 1, { locale: locale }),
      key: locale,
    })
  })
  return select
})

const handleChangeLocale = (value) => {
  store.setLocale(value)
  // reload page
  router.go()
}
</script>

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
