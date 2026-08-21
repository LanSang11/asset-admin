<template>
  <router-link class="top-brand" :to="homePath" :aria-label="`${title}首页`">
    <img class="top-brand__logo" :src="logoUrl" alt="系统标识" draggable="false" />
    <span class="top-brand__copy">
      <strong class="top-brand__title" :title="title">{{ title }}</strong>
      <span class="top-brand__portal">{{ portalLabel }}</span>
    </span>
  </router-link>
</template>

<script setup>
const props = defineProps({
  portal: {
    type: String,
    default: 'admin',
    validator: (value) => ['admin', 'work'].includes(value),
  },
})

const title = import.meta.env.VITE_TITLE || '资产管理系统'
const logoUrl = `${import.meta.env.BASE_URL}resource/company-logo.jpg`
const homePath = computed(() => (props.portal === 'work' ? '/work/home' : '/workbench'))
const portalLabel = computed(() => (props.portal === 'work' ? '业务工作台' : '管理中心'))
</script>

<style scoped>
.top-brand {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 12px;
  width: 236px;
  min-width: 0;
  min-height: 40px;
  color: #f8fafc;
  text-decoration: none;
}

.top-brand__logo {
  display: block;
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  object-position: center;
  background: #fff;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.24);
}

.top-brand__copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
}

.top-brand__title {
  max-width: 168px;
  overflow: hidden;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.15;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.top-brand__portal {
  color: #8aa6c4;
  font-size: 11px;
  line-height: 1;
}

@media (max-width: 1359.98px) {
  .top-brand {
    width: 204px;
  }

  .top-brand__title {
    max-width: 136px;
  }
}

@media (max-width: 767.98px) {
  .top-brand {
    width: 52px;
    gap: 0;
  }

  .top-brand__copy {
    display: none;
  }
}

@media (max-width: 479.98px) {
  .top-brand {
    width: 44px;
  }

  .top-brand__logo {
    flex-basis: 36px;
    width: 36px;
    height: 36px;
  }
}
</style>
