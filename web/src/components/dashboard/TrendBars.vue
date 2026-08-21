<template>
  <div v-if="normalizedItems.length" class="trend-bars" role="img" aria-label="近七天领用归还趋势">
    <div v-for="item in normalizedItems" :key="item.date" class="trend-bars__group">
      <div class="trend-bars__plot">
        <span
          class="trend-bars__bar trend-bars__bar--use"
          :style="barStyle(item['领用'])"
          :aria-label="`${item.date}领用${item['领用']}台`"
          role="img"
        />
        <span
          class="trend-bars__bar trend-bars__bar--return"
          :style="barStyle(item['归还'])"
          :aria-label="`${item.date}归还${item['归还']}台`"
          role="img"
        />
      </div>
      <span class="trend-bars__date">{{ item.date }}</span>
    </div>
  </div>
  <div v-else class="trend-bars__empty">暂无趋势数据</div>
</template>

<script setup>
import { computed } from 'vue'
import { getTrendBarHeight, getTrendMax } from '@/views/dashboard-model'

const props = defineProps({
  items: { type: Array, default: () => [] },
})

const normalizedItems = computed(() => props.items.slice(-7))
const max = computed(() => getTrendMax(normalizedItems.value))
const barStyle = (value) => ({ height: `${getTrendBarHeight(value, max.value)}%` })
</script>

<style scoped>
.trend-bars {
  display: grid;
  grid-template-columns: repeat(7, minmax(28px, 1fr));
  align-items: end;
  gap: 12px;
  min-height: 210px;
  overflow-x: auto;
}
.trend-bars__group {
  display: flex;
  min-width: 34px;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}
.trend-bars__plot {
  display: flex;
  align-items: flex-end;
  justify-content: center;
  gap: 5px;
  width: 100%;
  height: 170px;
  border-bottom: 1px solid var(--shell-border);
}
.trend-bars__bar {
  width: 10px;
  border-radius: 4px 4px 0 0;
  transition: height 180ms ease;
}
.trend-bars__bar--use {
  background: var(--shell-accent);
}
.trend-bars__bar--return {
  background: var(--shell-success);
}
.trend-bars__date {
  color: var(--shell-text-muted);
  font-size: 11px;
  white-space: nowrap;
}
.trend-bars__empty {
  display: grid;
  min-height: 180px;
  place-items: center;
  color: var(--shell-text-muted);
}
</style>
