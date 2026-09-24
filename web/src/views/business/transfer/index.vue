<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import { usePermissionStore, useUserStore } from '@/store'
import { canUseScanAction, resolveScannedAsset } from '@/utils/asset-qr'
import api from '@/api'
import { shouldShowLocalError } from '@/utils/http/validation-errors'

defineOptions({ name: '调拨管理' })

const $table = ref(null)
const queryItems = ref({ scope: 'all' })
const permissionStore = usePermissionStore()
const userStore = useUserStore()
const route = useRoute()

const applyVisible = ref(false)
const applyForm = ref({ asset_id: null, to_employee_id: null, reason: '' })
const applyLoading = ref(false)
const assetOptions = ref([])
const employeeOptions = ref([])
const scanAssetLocked = ref(false)
const scanAssetLabel = ref('')
const hasActiveEmployee = ref(false)

const approveVisible = ref(false)
const approveForm = ref({ transfer_id: null, approve: true, comment: '' })
const approveLoading = ref(false)

const statusMap = { 1: '待主管审批', 2: '待管理员审批', 3: '已通过', 4: '已驳回' }
const statusTagType = { 1: 'warning', 2: 'warning', 3: 'success', 4: 'error' }

function hasApi(p) {
  return (permissionStore.accessApis || []).includes(p)
}

const canApply = () => hasActiveEmployee.value && hasApi('post/api/v1/asset-transfer/apply')
const canApprove = () => hasApi('post/api/v1/asset-transfer/approve')

async function loadActionContext() {
  try {
    const res = await api.getAssetActionContext()
    hasActiveEmployee.value = res.data?.has_active_employee === true
  } catch (_) {
    hasActiveEmployee.value = false
  }
}

async function loadMyAssets() {
  const res = await api.getMyAssets()
  const assets = (res.data || []).filter((a) => a.status === 1)
  assetOptions.value = assets.map((a) => ({ label: `${a.asset_no} ${a.name}`, value: a.id }))
  return assets
}

async function loadAdminAssets() {
  const res = await api.getAssetList({
    page: 1,
    page_size: 100,
    status: 1,
  })
  const assets = (res.data?.list || []).filter((a) => a.status === 1 && a.owner_emp_id)
  assetOptions.value = assets.map((a) => ({ label: `${a.asset_no} ${a.name}`, value: a.id }))
  return assets
}

async function loadCandidates() {
  const res = await api.getTransferCandidates()
  employeeOptions.value = (res.data || []).map((e) => ({
    label: `${e.emp_no} ${e.name}${e.dept_name ? `（${e.dept_name}）` : ''}`,
    value: e.id,
  }))
}

async function openApply(scanQuery = null) {
  if (!canApply()) {
    if (scanQuery) $message.warning('当前账号没有发起调拨的权限。')
    return
  }
  applyForm.value = { asset_id: null, to_employee_id: null, reason: '' }
  scanAssetLocked.value = false
  scanAssetLabel.value = ''
  applyVisible.value = !scanQuery
  try {
    if (!scanQuery) {
      await Promise.all([
        hasApi('post/api/v1/asset/create') ? loadAdminAssets() : loadMyAssets(),
        loadCandidates(),
      ])
      return
    }
    const assetId = Array.isArray(scanQuery.asset_id) ? scanQuery.asset_id[0] : scanQuery.asset_id
    const [assetRes, contextRes] = await Promise.all([
      api.getAssetById({ id: assetId }),
      api.getAssetActionContext(),
    ])
    const scannedAsset = resolveScannedAsset([assetRes.data], scanQuery)
    hasActiveEmployee.value = contextRes.data?.has_active_employee === true
    const allowed = canUseScanAction('transfer', scannedAsset, {
      accessApis: permissionStore.accessApis || [],
      portal: userStore.portal,
      ownAssetIds: contextRes.data?.own_asset_ids || [],
      hasActiveEmployee: contextRes.data?.has_active_employee === true,
    })
    if (!allowed || !scannedAsset?.owner_emp_id) {
      applyVisible.value = false
      $message.warning('未找到这台可调拨资产，可能已变更状态或你当前无权操作。')
      return
    }
    await loadCandidates()
    assetOptions.value = [
      { label: `${scannedAsset.asset_no} ${scannedAsset.name}`, value: scannedAsset.id },
    ]
    applyForm.value.asset_id = scannedAsset.id
    scanAssetLocked.value = true
    scanAssetLabel.value = `${scannedAsset.asset_no} ${scannedAsset.name}`
    applyVisible.value = true
  } catch (error) {
    if (scanQuery) applyVisible.value = false
    if (shouldShowLocalError(error)) $message.error(error?.msg || error?.message || '可调拨资产加载失败，请稍后重试。')
  }
}

async function submitApply() {
  const reason = applyForm.value.reason?.trim() || ''
  if (
    !applyForm.value.asset_id ||
    !applyForm.value.to_employee_id ||
    !reason
  ) {
    $message.warning('请选择资产、调入人并填写说明')
    return
  }
  if (reason.length < 2) {
    $message.warning('调拨说明至少输入 2 个字符')
    return
  }
  if (applyLoading.value) return
  applyLoading.value = true
  try {
    await api.applyAssetTransfer({ ...applyForm.value, reason })
    $message.success('调拨已提交')
    applyVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    if (shouldShowLocalError(e)) $message.error(e?.msg || e?.message || '提交失败')
  } finally {
    applyLoading.value = false
  }
}

function openApprove(row, approve) {
  approveForm.value = { transfer_id: row.id, approve, comment: '' }
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
    const res = await api.approveAssetTransfer(approveForm.value)
    const st = res?.data?.status
    if (st === 2) $message.success('一级已通过，等待管理员终审')
    else if (st === 3) $message.success('已调拨，资产仍为在用')
    else if (st === 4) $message.success('已驳回')
    else $message.success('审批完成')
    approveVisible.value = false
    $table.value?.handleSearch()
  } catch (e) {
    if (shouldShowLocalError(e)) $message.error(e?.msg || e?.message || '审批失败')
  } finally {
    approveLoading.value = false
  }
}

const columns = [
  { title: '资产编号', key: 'asset_no', width: 110, align: 'center', fixed: 'left' },
  { title: '资产名称', key: 'asset_name', width: 140, align: 'center' },
  { title: '调出人', key: 'from_employee_name', width: 90, align: 'center' },
  { title: '调入人', key: 'to_employee_name', width: 90, align: 'center' },
  { title: '说明', key: 'reason', ellipsis: { tooltip: true } },
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
    width: 180,
    align: 'center',
    render: (row) => {
      if (!canApprove() || (row.status !== 1 && row.status !== 2)) return null
      return [
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
        ),
      ]
    },
  },
]

onMounted(async () => {
  $table.value?.handleSearch()
  await loadActionContext()
  if (route.query.asset_id || route.query.asset_no) openApply(route.query)
})
</script>

<template>
  <CommonPage>
    <template #action>
      <NButton v-if="canApply()" type="primary" @click="openApply()">申请调拨</NButton>
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAssetTransferList"
      :scroll-x="860"
    >
      <template #queryBar>
        <QueryBarItem label="范围" label-width="50">
          <NSelect
            v-model:value="queryItems.scope"
            :options="[
              { label: '默认', value: 'all' },
              { label: '我的', value: 'mine' },
              { label: '待我审', value: 'pending' },
            ]"
            style="width: 120px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <NModal
      v-model:show="applyVisible"
      preset="card"
      title="申请调拨"
      style="width: min(420px, calc(100vw - 24px))"
    >
      <NForm>
        <NFormItem label="资产">
          <div class="scan-prefill-control">
            <NSelect
              v-model:value="applyForm.asset_id"
              :options="assetOptions"
              filterable
              :disabled="scanAssetLocked"
              :placeholder="scanAssetLocked ? scanAssetLabel : '选择在用资产'"
            />
            <p v-if="scanAssetLocked" class="scan-prefill-hint">
              已从扫码结果带入：{{ scanAssetLabel }}
            </p>
          </div>
        </NFormItem>
        <NFormItem label="调入人">
          <NSelect
            v-model:value="applyForm.to_employee_id"
            :options="employeeOptions"
            filterable
            placeholder="选择调入员工"
          />
        </NFormItem>
        <NFormItem label="说明">
          <NInput v-model:value="applyForm.reason" type="textarea" :rows="3" maxlength="255" show-count placeholder="请说明调拨原因（至少 2 个字符）" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="applyVisible = false">取消</NButton>
        <NButton type="primary" :loading="applyLoading" @click="submitApply">提交</NButton>
      </template>
    </NModal>

    <NModal
      v-model:show="approveVisible"
      preset="card"
      title="审批调拨"
      style="width: min(400px, calc(100vw - 24px))"
    >
      <NForm>
        <NFormItem label="意见">
          <NInput v-model:value="approveForm.comment" type="textarea" :rows="3" maxlength="255" show-count />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="approveVisible = false">取消</NButton>
        <NButton type="primary" :loading="approveLoading" @click="submitApprove">确定</NButton>
      </template>
    </NModal>
  </CommonPage>
</template>

<style scoped>
.scan-prefill-control {
  display: grid;
  width: 100%;
  min-width: 0;
}
.scan-prefill-hint {
  margin: 6px 0 0;
  color: var(--shell-text-muted, #667085);
  font-size: 12px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
</style>
