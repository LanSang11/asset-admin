<template>
  <n-popover
    trigger="click"
    placement="bottom-end"
    :style="{ width: '340px', maxWidth: 'calc(100vw - 24px)' }"
  >
    <template #trigger>
      <button class="notification-trigger" type="button" aria-label="查看通知">
        <n-badge :value="unreadCount" :max="99" :show="unreadCount > 0">
          <n-icon size="18"><icon-mdi:bell-outline /></n-icon>
        </n-badge>
      </button>
    </template>
    <div class="notification-panel">
      <div class="notification-header">
        <span style="font-weight: bold">通知</span>
        <n-button text type="primary" size="small" @click="markAllRead">全部已读</n-button>
      </div>
      <div v-if="list.length === 0" class="notification-empty">暂无通知</div>
      <div
        v-for="item in list"
        :key="item.id"
        class="notification-item"
        :class="{ unread: !item.is_read }"
        @click="markRead(item)"
      >
        <div class="notification-title">
          <span>{{ item.title }}</span>
          <n-tag v-if="!item.is_read" size="tiny" type="warning">新</n-tag>
        </div>
        <div class="notification-content">{{ item.content }}</div>
        <div class="notification-time">{{ item.created_at }}</div>
      </div>
    </div>
  </n-popover>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/store'
import api from '@/api'

const unreadCount = ref(0)
const list = ref([])
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
let timer = null
let loading = false

/** ISO-A6：普通员工壳不展示审批待办（主管/管理员可看） */
function canSeeApprovalTask() {
  if (userStore.isSuperUser) return true
  const names = userStore.userInfo?.role_names || []
  if (names.includes('部门主管') || names.includes('管理员')) return true
  return false
}

function normalizeType(item) {
  if (item?.type) return item.type
  const text = `${item?.title || ''}${item?.content || ''}`
  if (/请审批|新的审批申请|待终审|待你审批/.test(text)) return 'approval_task'
  return 'applicant_progress'
}

function filterForViewer(items) {
  if (canSeeApprovalTask()) return items || []
  return (items || []).filter((i) => normalizeType(i) !== 'approval_task')
}

async function load() {
  // 修复：页面不可见（后台标签页）时暂停轮询；且同一时刻只允许一个请求（防并发堆积）
  if (document.hidden || loading) return
  // 修复：强制改密流程中（首次登录/密码被重置）通知接口不在白名单，轮询只会 403
  if (route.query.forceChangePassword) return
  loading = true
  try {
    // silent：轮询请求失败不弹全局错误（避免强制改密等场景每 30 秒弹一次 403）
    const res = await api.getUnreadCount()
    unreadCount.value = res.data?.count || 0
    const listRes = await api.getNotificationList({ page: 1, page_size: 10 })
    // 前端第二道闸：与服务端员工过滤叠加，防历史脏数据/角色误配
    list.value = filterForViewer(listRes.data?.list || [])
  } catch (e) {
    // 静默失败：网络抖动/权限未就绪时不打断用户
  } finally {
    loading = false
  }
}

function onVisibilityChange() {
  if (!document.hidden) {
    load()
  }
}

async function markRead(item) {
  // 先跳转再标已读（或并行）：通知携带 route 时点击跳转到对应业务页面
  // 安全：仅允许站内相对路由（以 / 开头且非 //、非 \\、非协议/查询/锚点前缀），防止未来 route 可被写入时开放重定向
  const safeRoute = item.route && /^\/(?!\/|\\|[:?#])/.test(item.route) ? item.route : ''
  if (item.is_read) {
    if (safeRoute) router.push(safeRoute)
    return
  }
  await api.markNotificationRead({ notification_id: item.id })
  item.is_read = true
  unreadCount.value = Math.max(0, unreadCount.value - 1)
  if (safeRoute) router.push(safeRoute)
}

async function markAllRead() {
  await api.markAllRead()
  unreadCount.value = 0
  list.value.forEach((i) => (i.is_read = true))
}

onMounted(() => {
  load()
  // 修复：每 30 秒轮询，但仅页面可见时执行（原无 hidden 判断、无卸载清理，
  // 后台标签页/多标签页持续轮询，且未登录状态下每 30 秒弹一次错误）
  timer = setInterval(load, 30000)
  document.addEventListener('visibilitychange', onVisibilityChange)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  document.removeEventListener('visibilitychange', onVisibilityChange)
})
</script>

<style scoped>
.notification-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  padding: 0;
  color: inherit;
  line-height: 1;
  cursor: pointer;
  background: transparent;
  border: 0;
  border-radius: 8px;
}

.notification-trigger:hover,
.notification-trigger:focus-visible {
  background: var(--topbar-action-hover, rgba(148, 163, 184, 0.18));
  outline: none;
}

.notification-trigger:focus-visible {
  box-shadow: 0 0 0 2px var(--shell-accent);
}

.notification-panel {
  max-height: 400px;
  overflow-y: auto;
  color: var(--shell-text);
}
.notification-empty {
  padding: 20px 0;
  color: var(--shell-text-muted);
  text-align: center;
}
.notification-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--shell-border);
  margin-bottom: 8px;
}
.notification-item {
  padding: 8px 6px;
  border-bottom: 1px solid var(--shell-border);
  color: var(--shell-text);
  cursor: pointer;
  border-radius: 4px;
}
.notification-item:hover {
  background: var(--shell-surface-muted);
}
.notification-item.unread {
  background: var(--shell-accent-soft);
}
.notification-title {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 500;
  font-size: 13px;
}
.notification-content {
  font-size: 12px;
  color: var(--shell-text-muted);
  margin: 4px 0;
}
.notification-time {
  font-size: 11px;
  color: var(--shell-text-muted);
}
</style>
