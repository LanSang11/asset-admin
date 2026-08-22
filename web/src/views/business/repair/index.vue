<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import { usePermissionStore } from '@/store'
import api from '@/api'

defineOptions({ name: '报修管理' })

const $table = ref(null)
const queryItems = ref({ scope: 'all' })
const permissionStore = usePermissionStore()

const applyVisible = ref(false)
const applyMode = ref('apply')
const applyForm = ref({ asset_id: null, reason: '', employee_id: null })
const applyLoading = ref(false)
const assetOptions = ref([])
const employeeOptions = ref([])
const statusLabel = { 1: '在用', 2: '闲置' }

const approveVisible = ref(false)
const approveForm = ref({ repair_id: null, approve: true, comment: '' })
const approveLoading = ref(false)

const completeVisible = ref(false)
const completeForm = ref({ repair_id: null, result: 'in_use', comment: '' })
const completeLoading = ref(false)

const statusMap = {
  1: '待主管审批',
  2: '待管理员审批',
  3: '维修中',
  4: '已修复',
  5: '已驳回',
}
const statusTagType = { 1: 'warning', 2: 'warning', 3: 'info', 4: 'success', 5: 'error' }

function hasApi(p) {
  return (permissionStore.accessApis || []).includes(p)
}

const canApply = () => hasApi('post/api/v1/asset-repair/apply')
const canApprove = () => hasApi('post/api/v1/asset-repair/approve')
const canComplete = () => hasApi('post/api/v1/asset-repair/complete')
const canRegister = () => hasApi('post/api/v1/asset-repair/register')

onMounted(() => {
  $table.value?.handleSearch()
})

async function loadMyAssets() {
  const res = await api.getMyAssets()
  assetOptions.value = (res.data || [])
    .filter((a) => a.status === 1)
    .map((a) => ({ label: `${a.asset_no} ${a.name}`, value: a.id }))
}

async function loadRegisterCandidates() {
  const res = await api.getAssetList({ page: 1, page_size: 100 })
  assetOptions.value = (res.data?.list || [])
    .filter((a) => a.status === 1 || a.status === 2)
    .map((a) => ({
      label: `${a.asset_no} ${a.name}（${statusLabel[a.status] || a.status}）`,
      value: a.id,
      owner_emp_id: a.owner_emp_id || null,
    }))
}

async function loadEmployees() {
  const res = await api.getEmployeeList({ page: 1, page_size: 100 })
  employeeOptions.value = (res.data?.list || [])
    .filter((e) => e.status !== false && e.status !== 0)
    .map((e) => ({ label: `${e.emp_no} ${e.name}`, value: e.id }))
}

function onRegisterAssetChange(id) {
  if (applyMode.value !== 'register') return
  const opt = assetOptions.value.find((a) => a.value === id)
  applyForm.value.employee_id = opt?.owner_emp_id || null
}

function openApply() {
  applyMode.value = 'apply'
  applyForm.value = { asset_id: null, reason: '', employee_id: null }
  applyVisible.value = true
  loadMyAssets()
}

function openRegister() {
  applyMode.value = 'register'
  applyForm.value = { asset_id: null, reason: '管理员登记送修', employee_id: null }
  applyVisible.value = true
  loadRegisterCandidates()
  loadEmployees()
}

async function submitApply() {
  if (!applyForm.value.asset_id || !applyForm.value.reason?.trim()) {
    $message.warning('请选择资产并填写故障说明')
    return
  }
  if (applyMode.value === 'register' && !applyForm.value.employee_id) {
    $message.warning('请指定报修人员工（闲置资产无领用人）')
    return
  }
  if (applyLoading.value) return
  applyLoading.value = true
  try {
    if (applyMode.value === 'register') {
      await api.registerAssetRepair({
        asset_id: applyForm.value.asset_id,
        reason: applyForm.value.reason,
        employee_id: applyForm.value.employee_id,
      })
      $message.success('已登记送修')
    } else {
      await api.applyAssetRepair({
        asset_id: applyForm.value.asset_id,
        reason: applyForm.value.reason,
      })
      $message.success('报修已提交')
    }
    applyVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    $message.error(e?.msg || e?.message || '提交失败')
  } finally {
    applyLoading.value = false
  }
}

function openApprove(row, approve) {
  approveForm.value = { repair_id: row.id, approve, comment: '' }
  approveVisible.value = true
}

async function submitApprove() {
  if (!approveForm.value.approve && !approveForm.value.comment.trim()) {
    $message.warning('驳回必须填写原因')
    return
  }
  if (approveLoading.value) return
  approveLoading.value = true
  try {
    const res = await api.approveAssetRepair(approveForm.value)
    const st = res?.data?.status
    if (st === 2) $message.success('一级已通过，等待管理员终审')
    else if (st === 3) $message.success('已进入维修')
    else if (st === 5) $message.success('已驳回')
    else $message.success('审批完成')
    approveVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    $message.error(e?.msg || e?.message || '审批失败')
  } finally {
    approveLoading.value = false
  }
}

function openComplete(row) {
  completeForm.value = { repair_id: row.id, result: 'in_use', comment: '' }
  completeVisible.value = true
}

async function submitComplete() {
  if (completeLoading.value) return
  completeLoading.value = true
  try {
    await api.completeAssetRepair(completeForm.value)
    $message.success('已登记修好')
    completeVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    $message.error(e?.msg || e?.message || '操作失败')
  } finally {
    completeLoading.value = false
  }
}

const columns = [
  { title: '资产编号', key: 'asset_no', width: 110, align: 'center' },
  { title: '资产名称', key: 'asset_name', width: 140, align: 'center' },
  { title: '报修人', key: 'employee_name', width: 90, align: 'center' },
  { title: '故障说明', key: 'reason', ellipsis: { tooltip: true } },
  {
    title: '状态',
    key: 'status',
    width: 120,
    align: 'center',
    render: (row) =>
      h(
        NTag,
        { type: statusTagType[row.status] || 'default', size: 'small' },
        () => statusMap[row.status] || row.status
      ),
  },
  {
    title: '操作',
    key: 'actions',
    width: 220,
    align: 'center',
    render: (row) => {
      const btns = []
      if (canApprove() && (row.status === 1 || row.status === 2)) {
        btns.push(
          h(
            NButton,
            { size: 'small', type: 'primary', onClick: () => openApprove(row, true) },
            () => '通过'
          ),
          h(
            NButton,
            {
              size: 'small',
              type: 'error',
              style: 'margin-left:6px',
              onClick: () => openApprove(row, false),
            },
            () => '驳回'
          )
        )
      }
      if (canComplete() && row.status === 3) {
        btns.push(
          h(
            NButton,
            {
              size: 'small',
              type: 'success',
              style: 'margin-left:6px',
              onClick: () => openComplete(row),
            },
            () => '修好'
          )
        )
      }
      return btns
    },
  },
]
</script>

<template>
  <CommonPage>
    <template #action>
      <NButton v-if="canApply()" type="primary" style="margin-right: 8px" @click="openApply"
        >我要报修</NButton
      >
      <NButton v-if="canRegister()" @click="openRegister">登记送修</NButton>
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAssetRepairList"
    >
      <template #queryBar>
        <QueryBarItem label="范围" label-width="50">
          <NSelect
            v-model:value="queryItems.scope"
            :options="[
              { label: '默认', value: 'all' },
              { label: '我的', value: 'mine' },
              { label: '待我审', value: 'pending' },
              { label: '维修中', value: 'repairing' },
            ]"
            style="width: 120px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <NModal
      v-model:show="applyVisible"
      preset="card"
      :title="applyMode === 'register' ? '登记送修' : '报修'"
      style="width: 420px"
    >
      <NForm>
        <NFormItem label="资产">
          <NSelect
            v-model:value="applyForm.asset_id"
            :options="assetOptions"
            filterable
            placeholder="选择资产"
            @update:value="onRegisterAssetChange"
          />
        </NFormItem>
        <NFormItem v-if="applyMode === 'register'" label="报修人">
          <NSelect
            v-model:value="applyForm.employee_id"
            :options="employeeOptions"
            filterable
            placeholder="闲置无领用人时必选"
          />
        </NFormItem>
        <NFormItem label="故障说明">
          <NInput v-model:value="applyForm.reason" type="textarea" :rows="3" maxlength="255" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="applyVisible = false">取消</NButton>
        <NButton type="primary" :loading="applyLoading" @click="submitApply">提交</NButton>
      </template>
    </NModal>

    <NModal v-model:show="approveVisible" preset="card" title="审批报修" style="width: 400px">
      <NForm>
        <NFormItem label="意见">
          <NInput v-model:value="approveForm.comment" type="textarea" :rows="3" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="approveVisible = false">取消</NButton>
        <NButton type="primary" :loading="approveLoading" @click="submitApprove">确定</NButton>
      </template>
    </NModal>

    <NModal v-model:show="completeVisible" preset="card" title="登记修好" style="width: 400px">
      <NForm>
        <NFormItem label="结果">
          <NSelect
            v-model:value="completeForm.result"
            :options="[
              { label: '交回领用人（在用）', value: 'in_use' },
              { label: '回闲置库', value: 'idle' },
            ]"
          />
        </NFormItem>
        <NFormItem label="备注">
          <NInput v-model:value="completeForm.comment" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="completeVisible = false">取消</NButton>
        <NButton type="primary" :loading="completeLoading" @click="submitComplete">确定</NButton>
      </template>
    </NModal>
  </CommonPage>
</template>
