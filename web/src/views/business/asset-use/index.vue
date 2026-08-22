<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NForm, NFormItem, NModal, NPopconfirm, NSelect, NTag } from 'naive-ui'
import { useDialog } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import { useUserStore } from '@/store'
import api from '@/api'
import { downloadFile } from '@/utils/download'

defineOptions({ name: '领用归还' })

const $table = ref(null)
const queryItems = ref({})
const userStore = useUserStore()
const dialog = useDialog()
const vPermission = resolveDirective('permission')

const applyVisible = ref(false)
const applyForm = ref({ asset_id: null, use_type: 1 })
const applyLoading = ref(false)
const assetOptions = ref([])
const historyVisible = ref(false)
const historyData = ref([])
const historyAssetName = ref('')

const statusMap = { 1: '待主管审批', 2: '待管理员审批', 3: '已通过', 4: '已驳回' }
const statusTagType = { 1: 'warning', 2: 'warning', 3: 'success', 4: 'error' }
const typeMap = { 1: '领用', 2: '归还' }

onMounted(() => {
  $table.value?.handleSearch()
})

async function loadAssets(useType) {
  // 修复：领用加载闲置资产；归还加载“我自己名下的在用资产”
  // （原实现归还也加载闲置资产，而闲置资产无 owner，永远选不到可归还项 → 归还功能不可用）
  if (useType === 2) {
    const res = await api.getMyAssets()
    assetOptions.value = (res.data || []).map((a) => ({
      label: `${a.asset_no} ${a.name}`,
      value: a.id,
    }))
  } else {
    const res = await api.getAssetList({ page: 1, page_size: 100 })
    assetOptions.value = (res.data?.list || [])
      .filter((a) => a.status === 2) // 只显示闲置资产可领用
      .map((a) => ({ label: `${a.asset_no} ${a.name}`, value: a.id }))
  }
}

function openApply(useType) {
  applyForm.value = { asset_id: null, use_type: useType }
  applyVisible.value = true
  loadAssets(useType)
}

async function submitApply() {
  if (!applyForm.value.asset_id) {
    $message.warning('请选择资产')
    return
  }
  if (applyLoading.value) return // 修复：防重复提交
  applyLoading.value = true
  // 修复：失败时给出页面级提示（原无 try/catch，失败无反馈）
  try {
    await api.applyAssetUse(applyForm.value)
    $message.success('申请已提交')
    applyVisible.value = false
    $table.value?.handleSearch()
  } catch (error) {
    $message.error(error?.msg || error?.message || '申请提交失败')
  } finally {
    applyLoading.value = false
  }
}

async function showHistory(row) {
  historyAssetName.value = `${row.asset_no} ${row.asset_name}`
  const res = await api.getAssetHistory({ asset_id: row.asset_id })
  historyData.value = res.data || []
  historyVisible.value = true
}

function handleExport() {
  downloadFile(
    '/export/asset-uses',
    {
      status: queryItems.status || 0,
      use_type: queryItems.use_type || 0,
    },
    '领用记录.csv',
    'export_asset_uses'
  )
}

const columns = [
  { title: '资产编号', key: 'asset_no', width: 110, align: 'center' },
  { title: '资产名称', key: 'asset_name', width: 140, align: 'center' },
  {
    title: '类型',
    key: 'use_type',
    width: 80,
    align: 'center',
    render: (row) => (row.use_type === 1 ? '领用' : '归还'),
  },
  { title: '申请人', key: 'employee_name', width: 100, align: 'center' },
  {
    title: '状态',
    key: 'status',
    width: 120,
    align: 'center',
    render: (row) =>
      h(
        NTag,
        { type: statusTagType[row.status] || 'default', size: 'small' },
        { default: () => statusMap[row.status] || row.status }
      ),
  },
  { title: '申请时间', key: 'apply_time', width: 160, align: 'center' },
  {
    title: '主管意见',
    key: 'manager_comment',
    width: 140,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '管理员意见',
    key: 'admin_comment',
    width: 140,
    align: 'center',
    ellipsis: { tooltip: true },
  },
  {
    title: '操作',
    key: 'actions',
    width: 120,
    align: 'center',
    render: (row) =>
      h(
        NButton,
        { size: 'small', type: 'info', onClick: () => showHistory(row) },
        { default: () => '历史追溯' }
      ),
  },
]
</script>

<template>
  <CommonPage>
    <template #action>
      <NButton
        v-permission="'get/api/v1/export/asset-uses'"
        style="margin-right: 8px"
        @click="handleExport"
        >导出 CSV</NButton
      >
      <NButton
        v-permission="'post/api/v1/asset-use/apply'"
        type="primary"
        style="margin-right: 8px"
        @click="openApply(1)"
        >申请领用</NButton
      >
      <NButton v-permission="'post/api/v1/asset-use/apply'" type="warning" @click="openApply(2)"
        >申请归还</NButton
      >
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAssetUseList"
    >
      <template #queryBar>
        <QueryBarItem label="状态" label-width="50">
          <NSelect
            v-model:value="queryItems.status"
            :options="[
              { label: '待主管审批', value: 1 },
              { label: '待管理员审批', value: 2 },
              { label: '已通过', value: 3 },
              { label: '已驳回', value: 4 },
            ]"
            clearable
            placeholder="全部"
            style="width: 130px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <!-- 申请弹窗 -->
    <NModal v-model:show="applyVisible" preset="card" title="资产申请" style="width: 480px">
      <NForm label-placement="left" label-width="80" :model="applyForm">
        <NFormItem :label="applyForm.use_type === 1 ? '选择资产' : '归还资产'">
          <NSelect
            v-model:value="applyForm.asset_id"
            :options="assetOptions"
            filterable
            :placeholder="applyForm.use_type === 1 ? '选择闲置资产' : '选择我名下的在用资产'"
          />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton type="primary" style="width: 100%" :loading="applyLoading" @click="submitApply">
          {{ applyForm.use_type === 1 ? '提交领用申请' : '提交归还申请' }}
        </NButton>
      </template>
    </NModal>

    <!-- 历史追溯弹窗 -->
    <NModal
      v-model:show="historyVisible"
      preset="card"
      :title="`资产历史：${historyAssetName}`"
      style="width: 640px"
    >
      <n-data-table
        :columns="[
          { title: '时间', key: 'use_time', width: 160 },
          { title: '类型', key: 'use_type_text', width: 70 },
          { title: '员工', key: 'employee_name', width: 90 },
          { title: '备注', key: 'remark' },
        ]"
        :data="historyData"
        :pagination="false"
        :bordered="false"
      />
    </NModal>
  </CommonPage>
</template>
