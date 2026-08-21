<template>
  <article class="metric-card" :class="`metric-card--${tone}`">
    <div class="metric-card__top">
      <span class="metric-card__label">{{ label }}</span>
      <span v-if="badge" class="metric-card__badge">{{ badge }}</span>
    </div>
    <div class="metric-card__value">{{ value }}</div>
    <div v-if="hint" class="metric-card__hint">{{ hint }}</div>
  </article>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: 0 },
  hint: { type: String, default: '' },
  tone: { type: String, default: 'primary' },
  badge: { type: String, default: '' },
})
</script>
