<template>
  <CommonPage title="我的资产">
    <CrudTable
      ref="$table"
      :columns="columns"
      :get-data="loadData"
      :query-items="{}"
      :scroll-x="900"
      :remote="false"
    />
    <NModal v-model:show="repairVisible" preset="card" title="报修" style="width: 400px">
      <NForm>
        <NFormItem label="故障说明">
          <NInput v-model:value="repairForm.reason" type="textarea" :rows="3" maxlength="255" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="repairVisible = false">取消</NButton>
        <NButton type="primary" :loading="repairLoading" @click="submitRepair">提交</NButton>
      </template>
    </NModal>
    <NModal v-model:show="transferVisible" preset="card" title="调拨" style="width: 420px">
      <NForm>
        <NFormItem label="调入人">
          <NSelect v-model:value="transferForm.to_employee_id" :options="employeeOptions" filterable placeholder="选择调入员工" />
        </NFormItem>
        <NFormItem label="说明">
          <NInput v-model:value="transferForm.reason" type="textarea" :rows="3" maxlength="255" />
        </NFormItem>
      </NForm>
      <template #footer>
        <NButton @click="transferVisible = false">取消</NButton>
        <NButton type="primary" :loading="transferLoading" @click="submitTransfer">提交</NButton>
      </template>
    </NModal>
    <AssetQrDialog v-model:show="qrVisible" :asset="qrAsset" />
  </CommonPage>
</template>

<script setup>
import { h, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { NButton, NForm, NFormItem, NInput, NModal, NSelect, NTag } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import CrudTable from '@/components/table/CrudTable.vue'
import AssetQrDialog from '@/components/asset/AssetQrDialog.vue'
import api from '@/api'

defineOptions({ name: 'WorkMyAssets' })

const router = useRouter()
const $table = ref(null)
const statusMap = { 1: '在用', 2: '闲置', 3: '维修', 4: '报废' }
const statusType = { 1: 'success', 2: 'info', 3: 'warning', 4: 'error' }
const warrantyTagType = { expired: 'error', expiring: 'warning', ok: 'success' }

const repairVisible = ref(false)
const repairForm = ref({ asset_id: null, reason: '' })
const repairLoading = ref(false)
const transferVisible = ref(false)
const transferForm = ref({ asset_id: null, to_employee_id: null, reason: '' })
const transferLoading = ref(false)
const employeeOptions = ref([])
const qrVisible = ref(false)
const qrAsset = ref(null)

function openQr(row) {
  qrAsset.value = row
  qrVisible.value = true
}

function openRepair(row) {
  repairForm.value = { asset_id: row.id, reason: '' }
  repairVisible.value = true
}

async function openTransfer(row) {
  transferForm.value = { asset_id: row.id, to_employee_id: null, reason: '' }
  transferVisible.value = true
  const res = await api.getTransferCandidates()
  employeeOptions.value = (res.data || []).map((e) => ({
    label: `${e.emp_no} ${e.name}${e.dept_name ? `（${e.dept_name}）` : ''}`,
    value: e.id,
  }))
}

async function submitTransfer() {
  if (!transferForm.value.to_employee_id || !transferForm.value.reason?.trim()) {
    $message.warning('请选择调入人并填写说明')
    return
  }
  if (transferLoading.value) return
  transferLoading.value = true
  try {
    await api.applyAssetTransfer(transferForm.value)
    $message.success('调拨已提交')
    transferVisible.value = false
    router.push('/work/transfer')
  } catch (e) {
    $message.error(e?.msg || e?.message || '调拨失败')
  } finally {
    transferLoading.value = false
  }
}

async function submitRepair() {
  if (!repairForm.value.reason?.trim()) {
    $message.warning('请填写故障说明')
    return
  }
  if (repairLoading.value) return
  repairLoading.value = true
  try {
    await api.applyAssetRepair(repairForm.value)
    $message.success('报修已提交')
    repairVisible.value = false
    router.push('/work/repair')
  } catch (e) {
    $message.error(e?.msg || e?.message || '报修失败')
  } finally {
    repairLoading.value = false
  }
}

const columns = [
  { title: '资产编号', key: 'asset_no', width: 140 },
  { title: '名称', key: 'name', ellipsis: { tooltip: true } },
  { title: '分类', key: 'category', width: 100 },
  {
    title: '状态',
    key: 'status',
    width: 90,
    render: (row) => h(NTag, { type: statusType[row.status] || 'default', size: 'small' }, () => statusMap[row.status] || row.status),
  },
  { title: '存放位置', key: 'location', ellipsis: { tooltip: true } },
  {
    title: '质保',
    key: 'warranty_until',
    width: 120,
    render: (row) =>
      row.warranty_label
        ? h(NTag, { size: 'small', type: warrantyTagType[row.warranty_state] || 'default' }, () => row.warranty_label)
        : row.warranty_until || '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    render: (row) => {
      const buttons = [
        h(NButton, { size: 'small', onClick: () => openQr(row) }, () => '二维码'),
      ]
      if (row.status === 1) {
        buttons.push(
          h(NButton, { size: 'small', type: 'warning', style: 'margin-left:6px', onClick: () => openRepair(row) }, () => '报修'),
          h(
            NButton,
            { size: 'small', type: 'primary', style: 'margin-left:6px', onClick: () => openTransfer(row) },
            () => '调拨',
          ),
        )
      }
      return buttons
    },
  },
]

async function loadData() {
  const res = await api.getMyAssets()
  const list = res.data || []
  return { data: list, total: list.length }
}

onMounted(() => {
  $table.value?.handleSearch()
})
</script>
