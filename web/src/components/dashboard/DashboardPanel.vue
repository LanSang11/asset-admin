<template>
  <section class="dashboard-panel">
    <header class="dashboard-panel__head">
      <div>
        <h2 class="dashboard-panel__title">{{ title }}</h2>
        <p v-if="subtitle" class="dashboard-panel__subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.action" class="dashboard-panel__action">
        <slot name="action" />
      </div>
    </header>
    <div class="dashboard-panel__body"><slot /></div>
  </section>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>
