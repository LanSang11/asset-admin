<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import CommonPage from '@/components/page/CommonPage.vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import DashboardPanel from '@/components/dashboard/DashboardPanel.vue'
import TrendBars from '@/components/dashboard/TrendBars.vue'
import SecurityPostureSection from '@/components/dashboard/SecurityPostureSection.vue'
import api from '@/api'
import {
  buildDashboardMetrics,
  buildSecurityDrillQuery,
  getDashboardScopeCopy,
  normalizeDashboardStats,
  normalizeSecurityPosture,
} from '@/views/dashboard-model'

defineOptions({ name: '统计看板' })

const router = useRouter()
const userStore = useUserStore()
const stats = ref(normalizeDashboardStats({ scope: 'self' }))
const posture = ref(normalizeSecurityPosture({}))
const loading = ref(false)
const postureError = ref(false)
const scope = computed(() => stats.value.scope)
const metrics = computed(() => buildDashboardMetrics(stats.value, scope.value))
const scopeCopy = computed(() => getDashboardScopeCopy(scope.value))
const showDepartment = computed(() => scope.value === 'company')
const showRanking = computed(() => scope.value !== 'self')

const percentage = (value) =>
  stats.value.total.assets
    ? Math.min(100, Math.round(((Number(value) || 0) / stats.value.total.assets) * 100))
    : 0

function openSecurityDrill(filter) {
  router.push({ path: '/system/security', query: buildSecurityDrillQuery(filter) })
}

async function load() {
  loading.value = true
  try {
    const response = await api.getDashboardStats()
    stats.value = normalizeDashboardStats(response?.data)
  } catch (_) {
    window.$message?.error('看板数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
  if (userStore.isSuperUser) {
    try {
      const response = await api.getSecurityPosture({ hours: 24 })
      posture.value = normalizeSecurityPosture(response?.data)
      postureError.value = false
    } catch (_) {
      postureError.value = true
    }
  }
}

onMounted(load)
</script>

<template>
  <CommonPage :show-header="false">
    <n-spin :show="loading">
      <div class="scope-heading">
        <div>
          <p>统计看板</p>
          <h1>{{ scopeCopy.subtitle }}</h1>
        </div>
        <n-tag size="small" :type="scope === 'company' ? 'info' : 'success'">{{ scope }}</n-tag>
      </div>

      <section class="ops-block" aria-label="资产运营">
        <h2 class="ops-block__title">资产运营</h2>
      <section class="dashboard-metrics" aria-label="统计指标">
        <MetricCard v-for="item in metrics" :key="item.key" v-bind="item" />
      </section>

      <div class="analytics-grid">
        <DashboardPanel title="资产分类占比" subtitle="当前数据范围">
          <div v-if="!stats.category_stats.length" class="panel-empty">暂无分类数据</div>
          <div v-else class="distribution-list">
            <div v-for="item in stats.category_stats" :key="item.name">
              <span>{{ item.name }}</span
              ><strong>{{ item.value }} 台</strong>
              <n-progress
                type="line"
                :percentage="percentage(item.value)"
                :height="8"
                :show-indicator="false"
              />
            </div>
          </div>
        </DashboardPanel>

        <DashboardPanel title="资产状态分布" subtitle="当前数据范围">
          <div v-if="!stats.status_stats.length" class="panel-empty">暂无状态数据</div>
          <div v-else class="distribution-list">
            <div v-for="item in stats.status_stats" :key="item.name">
              <span>{{ item.name }}</span
              ><strong>{{ item.value }} 台</strong>
              <n-progress
                type="line"
                :percentage="percentage(item.value)"
                :height="8"
                :show-indicator="false"
                color="#50b992"
              />
            </div>
          </div>
        </DashboardPanel>

        <DashboardPanel v-if="showDepartment" title="部门资产分布" subtitle="仅全公司口径展示">
          <div v-if="!stats.dept_stats.length" class="panel-empty">暂无部门数据</div>
          <div v-else class="distribution-list">
            <div v-for="item in stats.dept_stats" :key="item.name">
              <span>{{ item.name }}</span
              ><strong>{{ item.value }} 台</strong>
              <n-progress
                type="line"
                :percentage="percentage(item.value)"
                :height="8"
                :show-indicator="false"
                color="#e9a23b"
              />
            </div>
          </div>
        </DashboardPanel>

        <DashboardPanel
          class="analytics-grid__trend"
          title="近 7 天领用 / 归还"
          :subtitle="scopeCopy.subtitle"
        >
          <TrendBars :items="stats.trend" />
        </DashboardPanel>

        <DashboardPanel :title="scopeCopy.idleTitle" subtitle="业务返回的脱敏字段">
          <div class="table-scroll">
            <n-table :single-line="false" size="small">
              <thead>
                <tr>
                  <th>编号</th>
                  <th>名称</th>
                  <th>分类</th>
                  <th>位置</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!stats.idle_list.length">
                  <td colspan="4" class="empty-cell">暂无闲置资产</td>
                </tr>
                <tr v-for="asset in stats.idle_list" :key="asset.asset_no">
                  <td>{{ asset.asset_no }}</td>
                  <td>{{ asset.name }}</td>
                  <td>{{ asset.category || '-' }}</td>
                  <td>{{ asset.location || '-' }}</td>
                </tr>
              </tbody>
            </n-table>
          </div>
        </DashboardPanel>

        <DashboardPanel title="过保关注" subtitle="即将过保与已过保，不含报废">
          <div class="table-scroll">
            <n-table :single-line="false" size="small">
              <thead>
                <tr>
                  <th>编号</th>
                  <th>名称</th>
                  <th>到期日</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!stats.warranty.list.length">
                  <td colspan="4" class="empty-cell">当前范围没有过保资产</td>
                </tr>
                <tr v-for="asset in stats.warranty.list" :key="asset.asset_no">
                  <td>{{ asset.asset_no }}</td>
                  <td>{{ asset.name }}</td>
                  <td>{{ asset.warranty_until || '-' }}</td>
                  <td>{{ asset.warranty_state === 'expired' ? '已过保' : '即将过保' }}</td>
                </tr>
              </tbody>
            </n-table>
          </div>
        </DashboardPanel>

        <DashboardPanel v-if="showRanking" :title="scopeCopy.rankingTitle" subtitle="当前授权范围">
          <div v-if="!stats.ranking.length" class="panel-empty">暂无排行数据</div>
          <ol v-else class="ranking-list">
            <li v-for="(item, index) in stats.ranking" :key="`${item.name}-${index}`">
              <span>{{ index + 1 }}</span
              ><b>{{ item.name }}</b
              ><strong>{{ item.count }} 台</strong>
            </li>
          </ol>
        </DashboardPanel>
      </div>
      </section>

      <section v-if="userStore.isSuperUser" class="ops-block" aria-label="安全态势">
        <h2 class="ops-block__title">安全态势</h2>
        <p v-if="postureError" class="ops-block__hint">安全态势暂未更新</p>
        <SecurityPostureSection :posture="posture" @drill="openSecurityDrill" />
      </section>
    </n-spin>
  </CommonPage>
</template>

<style scoped>
.ops-block {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-top: 16px;
}
.ops-block__title {
  margin: 0;
  color: var(--shell-text);
  font-size: 16px;
}
.ops-block__hint {
  margin: 0;
  color: var(--shell-warning);
  font-size: 12px;
}
.scope-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.scope-heading p,
.scope-heading h1 {
  margin: 0;
}
.scope-heading p {
  color: var(--shell-accent);
  font-size: 12px;
  font-weight: 700;
}
.scope-heading h1 {
  margin-top: 3px;
  color: var(--shell-text);
  font-size: 24px;
}
.analytics-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}
.analytics-grid__trend {
  grid-column: 1 / -1;
}
.distribution-list {
  display: flex;
  flex-direction: column;
  gap: 13px;
}
.distribution-list > div {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 5px 12px;
  color: var(--shell-text);
  font-size: 13px;
}
.distribution-list .n-progress {
  grid-column: 1 / -1;
}
.panel-empty {
  min-height: 120px;
  display: grid;
  place-items: center;
  color: var(--shell-text-muted);
}
.table-scroll {
  max-width: 100%;
  overflow-x: auto;
}
.empty-cell {
  padding: 28px !important;
  color: var(--shell-text-muted);
  text-align: center;
}
.ranking-list {
  display: flex;
  margin: 0;
  padding: 0;
  flex-direction: column;
  gap: 8px;
  list-style: none;
}
.ranking-list li {
  display: grid;
  grid-template-columns: 30px 1fr auto;
  align-items: center;
  min-height: 34px;
  color: var(--shell-text);
}
.ranking-list li > span {
  display: inline-grid;
  width: 23px;
  height: 23px;
  place-items: center;
  border-radius: 6px;
  color: var(--shell-accent);
  background: var(--shell-accent-soft);
}
@media (max-width: 900px) {
  .analytics-grid {
    grid-template-columns: 1fr;
  }
  .analytics-grid__trend {
    grid-column: auto;
  }
}
</style>
