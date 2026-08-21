<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import { NButton, NInput, NModal, NSelect, NTag } from 'naive-ui'
import { useDialog } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import api from '@/api'

defineOptions({ name: '审批中心' })

const $table = ref(null)
const queryItems = ref({ scope: 'pending' })
const dialog = useDialog()
const vPermission = resolveDirective('permission')

const approveVisible = ref(false)
const approveForm = ref({ application_id: null, approve: true, comment: '' })
const approveLoading = ref(false)

const statusMap = { 1: '待主管审批', 2: '待管理员审批', 3: '已通过', 4: '已驳回' }
const statusTagType = { 1: 'warning', 2: 'warning', 3: 'success', 4: 'error' }

onMounted(() => {
  $table.value?.handleSearch()
})

function openApprove(row, approve) {
  approveForm.value = { application_id: row.id, approve, comment: '' }
  approveVisible.value = true
}

async function submitApprove() {
  // 修复：驳回必须填写原因（审批留痕，避免无理由驳回）；失败给出页面级提示
  if (!approveForm.value.approve && !approveForm.value.comment.trim()) {
    $message.warning('驳回必须填写原因')
    return
  }
  if (approveLoading.value) return // 修复：防重复提交
  approveLoading.value = true
  try {
    const res = await api.approveAssetUse(approveForm.value)
    const st = res?.data?.status
    // 按真实状态提示，避免「点了通过但资产未变」被误认为失败
    if (st === 2) {
      $message.success('一级审批已通过，请等待管理员终审')
    } else if (st === 3) {
      $message.success('审批通过，资产状态已更新')
    } else if (st === 4) {
      $message.success('已驳回')
    } else {
      $message.success('审批完成')
    }
    approveVisible.value = false
    $table.value?.handleSearch()
  } catch (error) {
    $message.error(error?.msg || error?.message || '审批失败')
  } finally {
    approveLoading.value = false
  }
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
    render: (row) => h(NTag, { type: statusTagType[row.status] || 'default', size: 'small' }, { default: () => statusMap[row.status] || row.status }),
  },
  { title: '申请时间', key: 'apply_time', width: 160, align: 'center' },
  {
    title: '操作',
    key: 'actions',
    width: 180,
    align: 'center',
    render: (row) => {
      const pending = row.status === 1 || row.status === 2
      if (!pending) return '-'
      // 修复：审批按钮加 v-permission（无权限用户不渲染按钮，而非点击后被后端 403）
      return [
        withDirectives(
          h(
            NButton,
            { size: 'small', type: 'success', style: 'margin-right:8px', onClick: () => openApprove(row, true) },
            { default: () => '通过' },
          ),
          [[vPermission, 'post/api/v1/asset-use/approve']]
        ),
        withDirectives(
          h(
            NButton,
            { size: 'small', type: 'error', onClick: () => openApprove(row, false) },
            { default: () => '驳回' },
          ),
          [[vPermission, 'post/api/v1/asset-use/approve']]
        ),
      ]
    },
  },
]
</script>

<template>
  <CommonPage>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAssetUseList"
    >
      <QueryBarItem label="范围" label-width="50">
        <NSelect
          v-model:value="queryItems.scope"
          :options="[
            { label: '待我审批', value: 'pending' },
            { label: '全部', value: 'all' },
            { label: '我的申请', value: 'mine' },
          ]"
          style="width: 130px"
          @update:value="$table?.handleSearch()"
        />
      </QueryBarItem>
    </CrudTable>

    <NModal v-model:show="approveVisible" preset="card" :title="approveForm.approve ? '审批通过' : '审批驳回'" style="width: 480px">
      <NInput
        v-model:value="approveForm.comment"
        type="textarea"
        :placeholder="approveForm.approve ? '审批意见（可选）' : '请填写驳回原因'"
        :rows="3"
      />
      <template #footer>
        <NButton :type="approveForm.approve ? 'success' : 'error'" style="width: 100%" :loading="approveLoading" @click="submitApprove">
          确认{{ approveForm.approve ? '通过' : '驳回' }}
        </NButton>
      </template>
    </NModal>
  </CommonPage>
</template>
