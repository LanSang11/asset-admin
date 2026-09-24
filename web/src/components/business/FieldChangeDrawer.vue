<script setup>
import { computed, ref, watch } from 'vue'
import {
  NDrawer,
  NDrawerContent,
  NEmpty,
  NPagination,
  NSpin,
  NTimeline,
  NTimelineItem,
} from 'naive-ui'

const props = defineProps({
  show: { type: Boolean, default: false },
  entityId: { type: Number, default: null },
  title: { type: String, default: '' },
  fetcher: { type: Function, required: true },
})

const emit = defineEmits(['update:show'])

const page = ref(1)
const pageSize = 20
const total = ref(0)
const changes = ref([])
const loading = ref(false)
let requestId = 0

const drawerTitle = computed(() => (props.title ? `${props.title} · 变更记录` : '变更记录'))

function clearChanges() {
  loading.value = false
  page.value = 1
  total.value = 0
  changes.value = []
}

function closeDrawer() {
  requestId += 1
  clearChanges()
  emit('update:show', false)
}

async function loadChanges(nextPage = 1) {
  if (!props.show || !props.entityId) return

  const entityId = props.entityId
  const currentRequestId = ++requestId
  loading.value = true

  try {
    const response = await props.fetcher({
      id: entityId,
      include_changes: true,
      change_page: nextPage,
      change_page_size: pageSize,
    })
    if (currentRequestId !== requestId || !props.show || props.entityId !== entityId) return

    const timeline = response.data?.changes || {}
    changes.value = timeline.list || []
    total.value = timeline.total || 0
    page.value = nextPage
  } catch (err) {
    if (currentRequestId === requestId && props.show && props.entityId === entityId) {
      $message.error(err?.msg || err?.message || '变更记录加载失败')
    }
  } finally {
    if (currentRequestId === requestId) loading.value = false
  }
}

watch(
  () => [props.show, props.entityId],
  ([show, entityId]) => {
    requestId += 1
    if (!show) {
      clearChanges()
      return
    }
    if (!entityId) {
      clearChanges()
      return
    }
    clearChanges()
    loadChanges(1)
  },
  { immediate: true }
)
</script>

<template>
  <NDrawer
    :show="show"
    width="520"
    @update:show="(visible) => (visible ? emit('update:show', true) : closeDrawer())"
  >
    <NDrawerContent :title="drawerTitle" closable>
      <NSpin :show="loading">
        <NEmpty v-if="!changes.length" description="暂无变更记录" />
        <NTimeline v-else>
          <NTimelineItem v-for="change in changes" :key="change.id" :title="change.changed_at">
            <div>{{ change.field_label }}</div>
            <div>{{ change.old_value || '未填写' }} → {{ change.new_value || '未填写' }}</div>
            <div>操作人：{{ change.operator_name || '系统' }}</div>
          </NTimelineItem>
        </NTimeline>
      </NSpin>
      <div v-if="total > pageSize" class="pagination">
        <NPagination
          :page="page"
          :item-count="total"
          :page-size="pageSize"
          @update:page="loadChanges"
        />
      </div>
    </NDrawerContent>
  </NDrawer>
</template>

<style scoped>
.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
