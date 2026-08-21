<template>
  <AppPage :show-footer="false">
    <div class="operations-dashboard">
      <header class="operations-intro">
        <div>
          <p class="operations-intro__eyebrow">数据运营总览</p>
          <h1>你好，{{ userStore.name }}</h1>
          <p>资产、审批与流转数据均来自当前业务口径。</p>
        </div>
        <div class="operations-intro__actions">
          <n-button v-if="canCreateAsset" type="primary" @click="openAssetCreate">
            <template #icon><TheIcon icon="mdi:plus" :size="18" /></template>
            新增资产
          </n-button>
          <div class="operations-intro__status" :class="{ 'is-warning': dashboardError }">
            <span class="operations-intro__dot" />
            {{ dashboardError ? '部分统计暂未更新' : '运营数据已同步' }}
          </div>
        </div>
      </header>

      <section class="ops-block" aria-label="资产运营">
        <h2 class="ops-block__title">资产运营</h2>
      <section class="dashboard-metrics" aria-label="关键运营指标">
        <MetricCard v-for="item in metrics" :key="item.key" v-bind="item" />
      </section>

      <div class="operations-layout">
        <DashboardPanel
          class="operations-layout__trend"
          title="近 7 天资产流转"
          subtitle="领用 / 归还"
        >
          <TrendBars :items="stats.trend" />
        </DashboardPanel>

        <DashboardPanel title="快捷处理" subtitle="按现有业务路由进入">
          <div class="quick-actions">
            <button
              v-for="item in quickActions"
              :key="item.path"
              type="button"
              @click="router.push(item.path)"
            >
              <span class="quick-actions__icon"><TheIcon :icon="item.icon" :size="20" /></span>
              <span>
                <strong>{{ item.title }}</strong>
                <small>{{ item.description }}</small>
              </span>
              <TheIcon icon="mdi:chevron-right" :size="18" />
            </button>
          </div>
        </DashboardPanel>

        <DashboardPanel title="近期闲置资产" :subtitle="scopeCopy.idleTitle">
          <div class="table-scroll">
            <n-table :single-line="false" size="small">
              <thead>
                <tr>
                  <th>资产编号</th>
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
                  <th>资产编号</th>
                  <th>名称</th>
                  <th>到期日</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                <tr v-if="!stats.warranty.list.length">
                  <td colspan="4" class="empty-cell">当前没有过保资产</td>
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

        <DashboardPanel
          title="资产归属排行"
          :subtitle="scopeCopy.rankingTitle || '当前口径不展示排行'"
        >
          <ol v-if="stats.ranking.length" class="ranking-list">
            <li v-for="(item, index) in stats.ranking" :key="`${item.name}-${index}`">
              <span class="ranking-list__index">{{ index + 1 }}</span>
              <span>{{ item.name }}</span>
              <strong>{{ item.count }} 台</strong>
            </li>
          </ol>
          <div v-else class="panel-empty">暂无排行数据</div>
        </DashboardPanel>
      </div>
      </section>

      <section v-if="userStore.isSuperUser" class="ops-block" aria-label="安全态势">
        <h2 class="ops-block__title">安全态势</h2>
        <p v-if="postureError" class="ops-block__hint">安全态势暂未更新</p>
        <SecurityPostureSection :posture="posture" @drill="openSecurityDrill" />
      </section>
    </div>
  </AppPage>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { usePermissionStore, useUserStore } from '@/store'
import api from '@/api'
import TheIcon from '@/components/icon/TheIcon.vue'
import AppPage from '@/components/page/AppPage.vue'
import MetricCard from '@/components/dashboard/MetricCard.vue'
import DashboardPanel from '@/components/dashboard/DashboardPanel.vue'
import TrendBars from '@/components/dashboard/TrendBars.vue'
import SecurityPostureSection from '@/components/dashboard/SecurityPostureSection.vue'
import { buildAdminMenuModels } from '@/layout/navigation/menu-model'
import {
  buildDashboardMetrics,
  buildSecurityDrillQuery,
  getDashboardScopeCopy,
  normalizeDashboardStats,
  normalizeSecurityPosture,
} from '@/views/dashboard-model'

defineOptions({ name: 'Workbench' })

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const stats = ref(normalizeDashboardStats({ scope: 'company' }))
const dashboardError = ref(false)
const posture = ref(normalizeSecurityPosture({}))
const postureError = ref(false)
const metrics = computed(() => buildDashboardMetrics(stats.value, stats.value.scope))
const scopeCopy = computed(() => getDashboardScopeCopy(stats.value.scope))

const quickActionDefinitions = [
  {
    title: '资产管理',
    description: '登记、编辑与盘点资产',
    path: '/business/asset',
    icon: 'mdi:desktop-classic',
  },
  {
    title: '领用归还',
    description: '查看流转与待处理记录',
    path: '/business/asset-use',
    icon: 'mdi:swap-horizontal',
  },
  {
    title: '审批中心',
    description: '处理当前审批事项',
    path: '/business/approval',
    icon: 'mdi:clipboard-check-outline',
  },
  {
    title: '统计看板',
    description: '查看完整业务口径',
    path: '/business/dashboard',
    icon: 'mdi:chart-box-outline',
  },
]

function collectMenuPaths(models, paths = new Set()) {
  for (const model of models) {
    if (model.path) paths.add(model.path)
    if (model.children?.length) collectMenuPaths(model.children, paths)
  }
  return paths
}

const availableMenuPaths = computed(() =>
  collectMenuPaths(buildAdminMenuModels(permissionStore.menus || []))
)
const canCreateAsset = computed(() => availableMenuPaths.value.has('/business/asset'))
const quickActions = computed(() =>
  quickActionDefinitions.filter((item) => availableMenuPaths.value.has(item.path))
)

function openAssetCreate() {
  router.push('/business/asset')
}

function openSecurityDrill(filter) {
  router.push({ path: '/system/security', query: buildSecurityDrillQuery(filter) })
}

onMounted(async () => {
  try {
    const response = await api.getDashboardStats()
    stats.value = normalizeDashboardStats(response?.data)
  } catch (_) {
    dashboardError.value = true
  }
  if (userStore.isSuperUser) {
    try {
      const response = await api.getSecurityPosture({ hours: 24 })
      posture.value = normalizeSecurityPosture(response?.data)
    } catch (_) {
      postureError.value = true
    }
  }
})
</script>

<style scoped>
.operations-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.ops-block {
  display: flex;
  flex-direction: column;
  gap: 16px;
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
.operations-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}
.operations-intro h1 {
  margin: 2px 0 4px;
  color: var(--shell-text);
  font-size: clamp(24px, 3vw, 34px);
  line-height: 1.2;
}
.operations-intro p {
  margin: 0;
  color: var(--shell-text-muted);
}
.operations-intro__eyebrow {
  color: var(--shell-accent) !important;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}
.operations-intro__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  flex-wrap: wrap;
}
.operations-intro__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 10px;
  border: 1px solid var(--shell-border);
  border-radius: 8px;
  color: var(--shell-text-muted);
  background: var(--shell-surface);
  font-size: 12px;
}
.operations-intro__dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--shell-success);
}
.operations-intro__status.is-warning .operations-intro__dot {
  background: var(--shell-warning);
}
.operations-layout {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
  gap: 16px;
}
.operations-layout__trend {
  min-height: 310px;
}
.quick-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.quick-actions button {
  display: grid;
  grid-template-columns: 36px minmax(0, 1fr) 20px;
  align-items: center;
  gap: 10px;
  min-height: 70px;
  padding: 10px;
  border: 1px solid var(--shell-border);
  border-radius: 9px;
  color: var(--shell-text);
  background: var(--shell-surface-muted);
  text-align: left;
  cursor: pointer;
}
.quick-actions button:hover {
  border-color: var(--shell-accent);
}
.quick-actions__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 8px;
  color: var(--shell-accent);
  background: var(--shell-accent-soft);
}
.quick-actions strong,
.quick-actions small {
  display: block;
}
.quick-actions small {
  margin-top: 3px;
  overflow: hidden;
  color: var(--shell-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
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
  grid-template-columns: 28px 1fr auto;
  align-items: center;
  min-height: 34px;
  color: var(--shell-text);
}
.ranking-list__index {
  display: inline-grid;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 6px;
  color: var(--shell-accent);
  background: var(--shell-accent-soft);
  font-size: 12px;
}
.table-scroll {
  max-width: 100%;
  overflow-x: auto;
}
.empty-cell,
.panel-empty {
  padding: 28px !important;
  color: var(--shell-text-muted);
  text-align: center;
}
@media (max-width: 1023px) {
  .operations-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .operations-intro {
    align-items: flex-start;
    flex-direction: column;
  }
  .operations-intro__actions {
    justify-content: flex-start;
  }
  .quick-actions {
    grid-template-columns: 1fr;
  }
}
</style>
