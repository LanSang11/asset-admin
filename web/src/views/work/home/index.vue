<template>
  <AppPage :show-footer="false">
    <div class="work-dashboard">
      <header class="work-intro">
        <div class="work-intro__identity">
          <img :src="userStore.avatar" alt="头像" />
          <div>
            <p>我的工作台</p>
            <h1>你好，{{ userStore.name }}</h1>
            <span>{{ roleHeadline }}</span>
          </div>
        </div>
        <p class="work-intro__hint">{{ roleHint }}</p>
      </header>

      <div v-if="dashboardError" class="dashboard-notice" role="status">
        统计摘要暂未更新，其他业务仍可正常使用。
      </div>

      <section class="dashboard-metrics" aria-label="工作台指标">
        <MetricCard v-for="item in metrics" :key="item.key" v-bind="item" />
      </section>

      <div class="work-layout">
        <DashboardPanel title="我的待办" subtitle="按当前角色能力展示">
          <div v-if="!todos.length" class="panel-empty">当前没有待办事项</div>
          <div v-else class="todo-list">
            <button
              v-for="todo in todos"
              :key="`${todo.path}-${todo.title}`"
              type="button"
              @click="router.push(todo.path)"
            >
              <span>{{ todo.title }}</span
              ><n-tag size="small" :type="todo.type">{{ todo.count }}</n-tag>
            </button>
          </div>
        </DashboardPanel>

        <DashboardPanel class="work-layout__quick" title="快捷入口" subtitle="只显示已开通能力">
          <div class="quick-grid">
            <button
              v-for="item in quickLinks"
              :key="item.path"
              type="button"
              @click="router.push(item.path)"
            >
              <span class="quick-grid__icon"><TheIcon :icon="item.icon" :size="22" /></span>
              <span
                ><strong>{{ item.title }}</strong
                ><small>{{ item.desc }}</small></span
              >
              <TheIcon icon="mdi:chevron-right" :size="18" />
            </button>
          </div>
        </DashboardPanel>
      </div>
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
import { buildDashboardMetrics, normalizeDashboardStats } from '@/views/dashboard-model'

defineOptions({ name: 'WorkHome' })

const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const stats = ref(normalizeDashboardStats({ scope: 'self' }))
const todos = ref([])
const dashboardError = ref(false)

function hasApi(path) {
  return (permissionStore.accessApis || []).includes(path)
}

const roleNames = computed(() => {
  const info = userStore.userInfo || {}
  if (Array.isArray(info.role_names) && info.role_names.length) return info.role_names
  return (info.roles || [])
    .map((role) => (typeof role === 'string' ? role : role?.name))
    .filter(Boolean)
})
const isManagerCap = computed(() => hasApi('post/api/v1/asset-use/approve'))
const roleHeadline = computed(() => {
  if (isManagerCap.value) return '部门主管 · 本部门审批与员工自助'
  if (roleNames.value.includes('普通用户')) return '普通用户 · 与普通员工同权'
  return '普通员工 · 领用归还、我的资产与申请进度'
})
const roleHint = computed(() =>
  isManagerCap.value
    ? '可处理本部门待审事项，并使用员工自助功能。'
    : '可发起领用、归还、报修和调拨，并查看个人统计摘要。'
)
const metrics = computed(() => buildDashboardMetrics(stats.value, stats.value.scope))

const quickLinks = computed(() => {
  const links = []
  if (hasApi('post/api/v1/asset-use/apply') || hasApi('get/api/v1/asset-use/list'))
    links.push({
      title: '领用归还',
      path: '/work/asset-use',
      icon: 'mdi:swap-horizontal',
      desc: '申请、归还与进度',
    })
  if (hasApi('get/api/v1/asset/my'))
    links.push({
      title: '我的资产',
      path: '/work/my-assets',
      icon: 'mdi:desktop-classic',
      desc: '查看在用与维修资产',
    })
  if (hasApi('post/api/v1/asset-repair/apply') || hasApi('get/api/v1/asset-repair/list'))
    links.push({
      title: '报修',
      path: '/work/repair',
      icon: 'mdi:wrench-outline',
      desc: '设备报修与进度',
    })
  if (hasApi('post/api/v1/asset-transfer/apply') || hasApi('get/api/v1/asset-transfer/list'))
    links.push({
      title: '调拨',
      path: '/work/transfer',
      icon: 'mdi:swap-horizontal-circle-outline',
      desc: '在用资产转给他人',
    })
  if (hasApi('get/api/v1/inventory/list') || hasApi('post/api/v1/inventory/count'))
    links.push({
      title: '盘点',
      path: '/work/inventory',
      icon: 'mdi:clipboard-text-outline',
      desc: '对账账面资产，记录盘亏',
    })
  if (hasApi('post/api/v1/kb/ask') || hasApi('get/api/v1/kb/list'))
    links.push({
      title: '知识库',
      path: '/work/kb',
      icon: 'mdi:book-open-page-variant-outline',
      desc: '操作说明问答，回答带引用',
    })
  if (hasApi('post/api/v1/employee-attachment/upload'))
    links.push({
      title: '我的附件',
      path: '/work/files',
      icon: 'mdi:paperclip',
      desc: '上传个人资料附件',
    })
  if (hasApi('post/api/v1/asset-use/approve'))
    links.push({
      title: '审批中心',
      path: '/work/approval',
      icon: 'mdi:clipboard-check-outline',
      desc: '处理本部门待审事项',
    })
  if (hasApi('get/api/v1/dashboard/stats'))
    links.push({
      title: '统计看板',
      path: '/work/dashboard',
      icon: 'mdi:chart-box-outline',
      desc: stats.value.scope === 'self' ? '个人统计摘要' : '本部门统计摘要',
    })
  if (hasApi('post/api/v1/ai/chat'))
    links.push({
      title: 'AI 助手',
      path: '/work/ai',
      icon: 'mdi:robot-outline',
      desc: '业务问答与协助',
    })
  links.push({
    title: '个人中心',
    path: '/work/profile',
    icon: 'mdi:account-circle-outline',
    desc: '修改密码与资料',
  })
  return links
})

async function safeCount(enabled, request, todo) {
  if (!enabled) return null
  try {
    const response = await request()
    const total = Number(response?.data?.total) || 0
    return total ? { ...todo, count: total } : null
  } catch (_) {
    return null
  }
}

async function getMyInFlightTransferCount() {
  const responses = await Promise.all([
    api.getAssetTransferList({ page: 1, page_size: 1, scope: 'mine', status: 1 }),
    api.getAssetTransferList({ page: 1, page_size: 1, scope: 'mine', status: 2 }),
  ])
  const total = responses.reduce((sum, response) => sum + (Number(response?.data?.total) || 0), 0)
  return { data: { total } }
}

async function getMyInFlightAssetUseCount() {
  const responses = await Promise.all([
    api.getAssetUseList({ page: 1, page_size: 1, scope: 'mine', status: 1 }),
    api.getAssetUseList({ page: 1, page_size: 1, scope: 'mine', status: 2 }),
  ])
  const total = responses.reduce((sum, response) => sum + (Number(response?.data?.total) || 0), 0)
  return { data: { total } }
}

onMounted(async () => {
  try {
    const response = await api.getDashboardStats()
    stats.value = normalizeDashboardStats(response?.data)
  } catch (_) {
    dashboardError.value = true
  }

  const results = await Promise.all([
    safeCount(
      hasApi('post/api/v1/asset-use/approve'),
      () => api.getAssetUseList({ page: 1, page_size: 1, scope: 'pending' }),
      { title: '待我审批的领用/归还', path: '/work/approval', type: 'warning' }
    ),
    safeCount(hasApi('get/api/v1/asset-use/list'), getMyInFlightAssetUseCount, {
      title: '我的在途领用申请',
      path: '/work/asset-use',
      type: 'info',
    }),
    safeCount(
      hasApi('post/api/v1/asset-repair/approve'),
      () => api.getAssetRepairList({ page: 1, page_size: 1, scope: 'pending' }),
      { title: '待我审批的报修', path: '/work/repair', type: 'warning' }
    ),
    safeCount(
      hasApi('get/api/v1/asset-repair/list'),
      () => api.getAssetRepairList({ page: 1, page_size: 1, scope: 'repairing' }),
      { title: '维修中的设备', path: '/work/repair', type: 'error' }
    ),
    safeCount(
      hasApi('post/api/v1/asset-transfer/approve'),
      () => api.getAssetTransferList({ page: 1, page_size: 1, scope: 'pending' }),
      { title: '待我审批的调拨', path: '/work/transfer', type: 'warning' }
    ),
    safeCount(hasApi('get/api/v1/asset-transfer/list'), getMyInFlightTransferCount, {
      title: '我的在途调拨',
      path: '/work/transfer',
      type: 'info',
    }),
  ])
  const due = Number(stats.value.warranty?.expiring || 0) + Number(stats.value.warranty?.expired || 0)
  if (due) {
    results.push({
      title: stats.value.scope === 'self' ? '我的资产过保/即将过保' : '资产过保/即将过保',
      path: stats.value.scope === 'self' ? '/work/my-assets' : '/work/dashboard',
      count: due,
      type: Number(stats.value.warranty?.expired || 0) ? 'error' : 'warning',
    })
  }
  todos.value = results.filter(Boolean)
})
</script>

<style scoped>
.work-dashboard {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.work-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}
.work-intro__identity {
  display: flex;
  align-items: center;
  gap: 14px;
}
.work-intro__identity img {
  width: 52px;
  height: 52px;
  border: 2px solid var(--shell-surface);
  border-radius: 50%;
  object-fit: cover;
  box-shadow: var(--shell-shadow);
}
.work-intro__identity p,
.work-intro__identity h1,
.work-intro__identity span,
.work-intro__hint {
  margin: 0;
}
.work-intro__identity p {
  color: var(--shell-accent);
  font-size: 12px;
  font-weight: 700;
}
.work-intro__identity h1 {
  margin: 2px 0;
  color: var(--shell-text);
  font-size: 25px;
}
.work-intro__identity span,
.work-intro__hint {
  color: var(--shell-text-muted);
  font-size: 13px;
}
.work-intro__hint {
  max-width: 420px;
  text-align: right;
}
.dashboard-notice {
  padding: 10px 12px;
  border: 1px solid rgba(233, 162, 59, 0.45);
  border-radius: 8px;
  color: var(--shell-text);
  background: rgba(233, 162, 59, 0.1);
  font-size: 13px;
}
.work-layout {
  display: grid;
  grid-template-columns: minmax(260px, 0.75fr) minmax(0, 1.65fr);
  gap: 16px;
}
.todo-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.todo-list button,
.quick-grid button {
  border: 1px solid var(--shell-border);
  border-radius: 9px;
  color: var(--shell-text);
  background: var(--shell-surface-muted);
  cursor: pointer;
}
.todo-list button {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 8px 12px;
  text-align: left;
}
.quick-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 10px;
}
.quick-grid button {
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr) 20px;
  align-items: center;
  gap: 10px;
  min-height: 76px;
  padding: 10px;
  text-align: left;
}
.todo-list button:hover,
.quick-grid button:hover {
  border-color: var(--shell-accent);
}
.quick-grid__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 9px;
  color: var(--shell-accent);
  background: var(--shell-accent-soft);
}
.quick-grid strong,
.quick-grid small {
  display: block;
}
.quick-grid small {
  margin-top: 3px;
  overflow: hidden;
  color: var(--shell-text-muted);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.panel-empty {
  min-height: 120px;
  display: grid;
  place-items: center;
  color: var(--shell-text-muted);
}
@media (max-width: 900px) {
  .work-layout {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 600px) {
  .work-intro {
    align-items: flex-start;
    flex-direction: column;
  }
  .work-intro__hint {
    text-align: left;
  }
}
</style>
