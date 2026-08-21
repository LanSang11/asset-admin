<template>
  <div class="security-posture">
    <section class="dashboard-metrics" aria-label="安全态势指标：认证失败 login_failure 与扫描聚合">
      <button
        v-for="item in metrics"
        :key="item.key"
        type="button"
        class="security-posture__hit"
        @click="emit('drill', item.filter)"
      >
        <MetricCard v-bind="item" />
      </button>
    </section>

    <div class="security-posture__grid">
      <DashboardPanel title="近 24 小时攻击趋势" subtitle="点击柱子按该小时下钻">
        <div v-if="posture.hourly.length" class="hourly" role="img" aria-label="攻击小时趋势">
          <button
            v-for="item in posture.hourly"
            :key="item.hour"
            type="button"
            class="hourly__col"
            :title="`${hourLabel(item.hour)} 共 ${item.total} 次`"
            @click="emit('drill', item.filter)"
          >
            <span class="hourly__bar" :style="{ height: `${barHeight(item.total)}%` }" />
            <span class="hourly__label">{{ hourLabel(item.hour) }}</span>
          </button>
        </div>
        <div v-else class="panel-empty">暂无攻击聚合</div>
      </DashboardPanel>

      <DashboardPanel title="来源 Top" subtitle="按分钟桶合计，点击带同一筛选下钻">
        <ol v-if="posture.top_sources.length" class="source-list">
          <li v-for="item in posture.top_sources" :key="item.ip">
            <button type="button" @click="emit('drill', item.filter)">
              <span>{{ item.ip }}</span>
              <strong>{{ item.count }}</strong>
            </button>
          </li>
        </ol>
        <div v-else class="panel-empty">暂无来源</div>
      </DashboardPanel>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import DashboardPanel from '@/components/dashboard/DashboardPanel.vue'
import {
  buildSecurityPostureMetrics,
  getHourlyMax,
  getTrendBarHeight,
  normalizeSecurityPosture,
} from '@/views/dashboard-model'

const props = defineProps({
  posture: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['drill'])

const posture = computed(() => normalizeSecurityPosture(props.posture))
const metrics = computed(() => buildSecurityPostureMetrics(posture.value))
const hourlyMax = computed(() => getHourlyMax(posture.value.hourly))

function barHeight(value) {
  return getTrendBarHeight(value, hourlyMax.value)
}

function hourLabel(hour) {
  const text = String(hour || '')
  const match = text.match(/\s(\d{2}):/)
  return match ? `${match[1]}时` : text.slice(11, 16) || text
}
</script>

<style scoped>
.security-posture {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.security-posture__hit {
  padding: 0;
  border: 0;
  background: transparent;
  text-align: left;
  cursor: pointer;
}
.security-posture__hit :deep(.metric-card) {
  height: 100%;
}
.security-posture__grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr);
  gap: 16px;
}
.hourly {
  display: grid;
  grid-template-columns: repeat(24, minmax(8px, 1fr));
  align-items: end;
  gap: 4px;
  min-height: 180px;
}
.hourly__col {
  display: flex;
  min-width: 0;
  height: 170px;
  padding: 0;
  border: 0;
  flex-direction: column;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  background: transparent;
  cursor: pointer;
}
.hourly__bar {
  width: 100%;
  max-width: 10px;
  border-radius: 4px 4px 0 0;
  background: var(--shell-warning);
}
.hourly__label {
  color: var(--shell-text-muted);
  font-size: 10px;
  transform: scale(0.9);
}
.source-list {
  display: flex;
  margin: 0;
  padding: 0;
  flex-direction: column;
  gap: 8px;
  list-style: none;
}
.source-list button {
  display: flex;
  width: 100%;
  min-height: 34px;
  padding: 0;
  border: 0;
  align-items: center;
  justify-content: space-between;
  color: var(--shell-text);
  background: transparent;
  cursor: pointer;
}
.panel-empty {
  min-height: 120px;
  display: grid;
  place-items: center;
  color: var(--shell-text-muted);
}
@media (max-width: 900px) {
  .security-posture__grid {
    grid-template-columns: 1fr;
  }
  .hourly {
    overflow-x: auto;
  }
}
</style>
