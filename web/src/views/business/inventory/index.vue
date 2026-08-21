<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import { usePermissionStore } from '@/store'
import api from '@/api'

defineOptions({ name: '盘点' })

const $table = ref(null)
const $lines = ref(null)
const queryItems = ref({ status: 0 })
const lineQuery = ref({ session_id: null, result: '' })
const permissionStore = usePermissionStore()
const startVisible = ref(false)
const startForm = ref({ title: '', scope: 'all', dept_id: null, note: '' })
const deptOptions = ref([])
const startLoading = ref(false)
const linesVisible = ref(false)
const currentSession = ref(null)
const summary = ref(null)

const statusMap = { 1: '进行中', 2: '已结束' }
const resultMap = { '': '未盘', found: '相符', missing: '盘亏', mismatch: '不符' }
const resultTag = { '': 'default', found: 'success', missing: 'error', mismatch: 'warning' }
const bookStatus = { 1: '在用', 2: '闲置', 3: '维修', 4: '报废' }

function hasApi(p) {
  return (permissionStore.accessApis || []).includes(p)
}
const canStart = () => hasApi('post/api/v1/inventory/start')
const canCount = () => hasApi('post/api/v1/inventory/count')
const canClose = () => hasApi('post/api/v1/inventory/close')

onMounted(() => $table.value?.handleSearch())

async function loadDepts() {
  if (!hasApi('get/api/v1/dept/list')) return
  try {
    const res = await api.getDepts({ page: 1, page_size: 100 })
    const list = res.data?.list || res.data || []
    deptOptions.value = (Array.isArray(list) ? list : []).map((d) => ({ label: d.name, value: d.id }))
  } catch (_) {
    deptOptions.value = []
  }
}

function openStart() {
  startForm.value = { title: '', scope: 'all', dept_id: null, note: '' }
  startVisible.value = true
  loadDepts()
}

async function submitStart() {
  if (!startForm.value.title.trim()) {
    $message.warning('请填写盘点名称')
    return
  }
  if (startLoading.value) return
  startLoading.value = true
  try {
    const res = await api.startInventory(startForm.value)
    $message.success('盘点已开始')
    startVisible.value = false
    $table.value?.handleSearch()
    openLines(res.data)
  } catch (e) {
    $message.error(e?.msg || e?.message || '发起失败')
  } finally {
    startLoading.value = false
  }
}

async function openLines(row) {
  const res = await api.getInventory({ id: row.id })
  currentSession.value = res.data
  summary.value = res.data?.summary
  lineQuery.value = { session_id: row.id, result: '' }
  linesVisible.value = true
}

async function submitCount(row, result) {
  try {
    await api.countInventory({ line_id: row.id, result, note: row.note || '' })
    $message.success('已记录')
    const res = await api.getInventory({ id: currentSession.value.id })
    currentSession.value = res.data
    summary.value = res.data?.summary
    $lines.value?.handleSearch()
  } catch (e) {
    $message.error(e?.msg || e?.message || '记录失败')
  }
}

async function submitClose() {
  if (!currentSession.value?.id) return
  try {
    const res = await api.closeInventory({ session_id: currentSession.value.id })
    $message.success('盘点已结束。盘盈请走资产登记，盘亏不会自动报废')
    currentSession.value = res.data
    summary.value = res.data?.summary
    $table.value?.handleSearch()
  } catch (e) {
    $message.error(e?.msg || e?.message || '结束失败')
  }
}

const columns = [
  { title: '名称', key: 'title', ellipsis: { tooltip: true } },
  {
    title: '范围',
    key: 'scope',
    width: 90,
    align: 'center',
    render: (row) => (row.scope === 'dept' ? `部门#${row.dept_id || '-'}` : '全部'),
  },
  {
    title: '状态',
    key: 'status',
    width: 90,
    align: 'center',
    render: (row) =>
      h(NTag, { type: row.status === 1 ? 'warning' : 'success', size: 'small' }, () => statusMap[row.status] || row.status),
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    align: 'center',
    render: (row) => h(NButton, { size: 'small', onClick: () => openLines(row) }, () => '明细'),
  },
]

const lineColumns = [
  { title: '编号', key: 'asset_no', width: 130 },
  { title: '名称', key: 'asset_name', ellipsis: { tooltip: true } },
  {
    title: '账面状态',
    key: 'book_status',
    width: 80,
    render: (row) => bookStatus[row.book_status] || row.book_status,
  },
  { title: '账面领用人', key: 'book_owner_name', width: 100, render: (row) => row.book_owner_name || '-' },
  {
    title: '结果',
    key: 'result',
    width: 80,
    render: (row) =>
      h(NTag, { type: resultTag[row.result] || 'default', size: 'small' }, () => resultMap[row.result] ?? row.result),
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    render: (row) => {
      if (!canCount() || currentSession.value?.status !== 1) return null
      return [
        h(NButton, { size: 'small', type: 'primary', onClick: () => submitCount(row, 'found') }, () => '相符'),
        h(NButton, { size: 'small', type: 'error', style: 'margin-left:6px', onClick: () => submitCount(row, 'missing') }, () => '盘亏'),
        h(NButton, { size: 'small', style: 'margin-left:6px', onClick: () => submitCount(row, 'mismatch') }, () => '不符'),
      ]
    },
  },
]
</script>

<template>
  <CommonPage>
    <template #action>
      <NButton v-if="canStart()" type="primary" @click="openStart">发起盘点</NButton>
    </template>
    <p class="inv-hint">对账账面资产。盘盈请去资产管理里登记新资产；盘亏只记录，不会自动报废。</p>
    <CrudTable ref="$table" v-model:query-items="queryItems" :columns="columns" :get-data="api.getInventoryList">
      <QueryBarItem label="状态" label-width="50">
        <NSelect
          v-model:value="queryItems.status"
          :options="[
            { label: '全部', value: 0 },
            { label: '进行中', value: 1 },
            { label: '已结束', value: 2 },
          ]"
          style="width: 120px"
        />
      </QueryBarItem>
    </CrudTable>

    <NModal v-model:show="startVisible" preset="card" title="发起盘点" style="width: 420px">
      <NForm>
        <NFormItem label="名称">
          <NInput v-model:value="startForm.title" placeholder="例如 2026年8月全司盘点" />
        </NFormItem>
        <NFormItem label="范围">
          <NSelect
            v-model:value="startForm.scope"
            :options="[
              { label: '全部（不含报废）', value: 'all' },
              { label: '按部门（该部门员工名下）', value: 'dept' },
            ]"
          />
        </NFormItem>
        <NFormItem v-if="startForm.scope === 'dept'" label="部门">
          <NSelect v-model:value="startForm.dept_id" :options="deptOptions" placeholder="选择部门" clearable />
        </NFormItem>
        <NFormItem label="备注">
          <NInput v-model:value="startForm.note" type="textarea" :rows="2" maxlength="255" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="startVisible = false">取消</NButton>
        <NButton type="primary" :loading="startLoading" @click="submitStart">开始</NButton>
      </template>
    </NModal>

    <NModal v-model:show="linesVisible" preset="card" :title="currentSession?.title || '盘点明细'" style="width: 920px">
      <p v-if="summary" class="inv-sum">
        共 {{ summary.total }} · 未盘 {{ summary.pending }} · 相符 {{ summary.found }} · 盘亏 {{ summary.missing }} · 不符 {{ summary.mismatch }}
      </p>
      <CrudTable ref="$lines" v-model:query-items="lineQuery" :columns="lineColumns" :get-data="api.getInventoryLines">
        <QueryBarItem label="结果" label-width="50">
          <NSelect
            v-model:value="lineQuery.result"
            :options="[
              { label: '全部', value: '' },
              { label: '未盘', value: 'pending' },
              { label: '相符', value: 'found' },
              { label: '盘亏', value: 'missing' },
              { label: '不符', value: 'mismatch' },
            ]"
            style="width: 120px"
          />
        </QueryBarItem>
      </CrudTable>
      <template #footer>
        <NButton @click="linesVisible = false">关闭</NButton>
        <NButton v-if="canClose() && currentSession?.status === 1" type="primary" @click="submitClose">结束盘点</NButton>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.inv-hint,
.inv-sum {
  margin: 0 0 12px;
  font-size: 13px;
  opacity: 0.75;
}
</style>
