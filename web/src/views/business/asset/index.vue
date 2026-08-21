<script setup>
import { h, onMounted, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NInputNumber, NPopconfirm, NSelect, NTag } from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { useCRUD, withStepUp } from '@/composables'
import api from '@/api'
import { downloadFile } from '@/utils/download'
import AssetQrDialog from '@/components/asset/AssetQrDialog.vue'

defineOptions({ name: '资产管理' })

const $table = ref(null)
const queryItems = ref({})
const qrVisible = ref(false)
const qrAsset = ref(null)

function openQr(row) {
  qrAsset.value = row
  qrVisible.value = true
}

const {
  modalVisible,
  modalTitle,
  modalLoading,
  handleSave,
  modalForm,
  modalFormRef,
  handleEdit,
  handleDelete,
  handleAdd,
} = useCRUD({
  name: '资产',
  initForm: { category: '其他', status: 2, location: '', remark: '', price: null },
  doCreate: api.createAsset,
  doUpdate: api.updateAsset,
  doDelete: api.deleteAsset,
  stepUpDeleteKey: 'asset_delete',
  refresh: () => $table.value?.handleSearch(),
})

const categoryOptions = ref([])
const employeeOptions = ref([])

onMounted(() => {
  $table.value?.handleSearch()
  api.getAssetCategories().then((res) => {
    categoryOptions.value = (res.data || []).map((c) => ({ label: c, value: c }))
  })
  api.getEmployeeList({ page: 1, page_size: 100 }).then((res) => {
    employeeOptions.value = (res.data?.list || []).map((e) => ({ label: `${e.emp_no} ${e.name}`, value: e.id }))
  })
})

const statusMap = { 1: '在用', 2: '闲置', 3: '维修', 4: '报废' }
const statusOptions = [
  { label: '在用', value: 1 },
  { label: '闲置', value: 2 },
  { label: '维修', value: 3 },
  { label: '报废', value: 4 },
]
const warrantyOptions = [
  { label: '即将过保', value: 'expiring' },
  { label: '已过保', value: 'expired' },
  { label: '过保关注', value: 'due' },
  { label: '在保', value: 'ok' },
  { label: '未填质保', value: 'none' },
]
const warrantyTagType = { expired: 'error', expiring: 'warning', ok: 'success' }

const rules = {
  asset_no: [{ required: true, message: '请输入资产编号', trigger: ['input', 'blur'] }],
  name: [{ required: true, message: '请输入资产名称', trigger: ['input', 'blur'] }],
}

const columns = [
  { title: '资产编号', key: 'asset_no', width: 110, align: 'center' },
  { title: '资产名称', key: 'name', width: 140, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '分类',
    key: 'category',
    width: 100,
    align: 'center',
    render: (row) => (row.category ? row.category : '-'),
  },
  { title: '型号', key: 'model', width: 120, align: 'center', ellipsis: { tooltip: true } },
  { title: '序列号', key: 'serial_no', width: 130, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '采购日期',
    key: 'purchase_date',
    width: 105,
    align: 'center',
    render: (row) => row.purchase_date || '-',
  },
  {
    title: '质保',
    key: 'warranty_until',
    width: 120,
    align: 'center',
    render: (row) =>
      row.warranty_label
        ? h(NTag, { size: 'small', type: warrantyTagType[row.warranty_state] || 'default' }, () => row.warranty_label)
        : row.warranty_until || '-',
  },
  {
    title: '价格(元)',
    key: 'price',
    width: 100,
    align: 'center',
    render: (row) => (row.price ? row.price : '-'),
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    align: 'center',
    render: (row) => statusMap[row.status] || '-',
  },
  { title: '存放位置', key: 'location', width: 110, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '当前领用人',
    key: 'owner_emp_id',
    width: 120,
    align: 'center',
    render: (row) => employeeOptions.value.find((e) => e.value === row.owner_emp_id)?.label || '-',
  },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    align: 'center',
    render: (row) => [
      h(
        NButton,
        {
          size: 'small',
          onClick: () => openQr(row),
        },
        { default: () => '二维码' },
      ),
      h(
        NButton,
        {
          size: 'small',
          type: 'primary',
          style: 'margin-left:8px',
          onClick: () => handleEdit(row),
        },
        { default: () => '编辑' },
      ),
      h(
        NPopconfirm,
        {
          onPositiveClick: () => handleDelete({ asset_id: row.id }),
        },
        {
          trigger: () =>
            h(
              NButton,
              { size: 'small', type: 'error', style: 'margin-left:8px' },
              { default: () => '删除' },
            ),
          default: () => `确定删除资产「${row.name}」吗？`,
        },
      ),
    ],
  },
]

function addAsset() {
  modalForm.value = { category: '其他', status: 2, location: '', remark: '', price: null }
  handleAdd()
}

function handleExport() {
  downloadFile(
    '/export/assets',
    {
      keyword: queryItems.value.keyword || '',
      category: queryItems.value.category || '',
      status: queryItems.value.status || 0,
    },
    '资产数据.csv',
    'export_assets'
  )
}

const fileInputRef = ref(null)
function pickImport() {
  fileInputRef.value?.click()
}

async function onImportFile(e) {
  const file = e.target.files?.[0]
  e.target.value = ''
  if (!file) return
  const fd = new FormData()
  fd.append('file', file)
  try {
    const preview = await api.importAssets(fd, 0)
    const d = preview.data || {}
    const msg = `预检：可导入 ${d.ok || 0}，跳过 ${d.skipped || 0}，错误 ${d.errors || 0}`
    if (!(d.ok > 0)) {
      $message.warning(msg + (d.error_rows?.[0] ? `；首错：第${d.error_rows[0].line}行 ${d.error_rows[0].reason}` : ''))
      return
    }
    await $dialog.confirm({
      title: '确认导入',
      type: 'warning',
      content: `${msg}。是否写入数据库？重复编号会跳过。`,
      async confirm() {
        try {
          const fd2 = new FormData()
          fd2.append('file', file)
          const done = await withStepUp('asset_import_commit', (headers) =>
            api.importAssets(fd2, 1, headers)
          )
          $message.success(`已写入 ${done.data?.created || 0} 条`)
          $table.value?.handleSearch()
        } catch (commitErr) {
          $message.error(commitErr?.msg || commitErr?.message || '写入失败')
          throw commitErr
        }
      },
    })
  } catch (err) {
    $message.error(err?.msg || err?.message || '导入失败')
  }
}
</script>

<template>
  <CommonPage>
    <template #action>
      <input ref="fileInputRef" type="file" accept=".csv,text/csv" style="display: none" @change="onImportFile" />
      <NButton style="margin-right: 8px" @click="handleExport">导出 CSV</NButton>
      <NButton style="margin-right: 8px" @click="pickImport">导入 CSV</NButton>
      <NButton type="primary" @click="addAsset">新增资产</NButton>
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getAssetList"
    >
      <QueryBarItem label="关键词" label-width="60">
        <NInput
          v-model:value="queryItems.keyword"
          type="text"
          clearable
          placeholder="名称/编号/序列号"
          style="width: 180px"
          @keydown.enter="$table?.handleSearch()"
        />
      </QueryBarItem>
      <QueryBarItem label="分类" label-width="50">
        <NSelect
          v-model:value="queryItems.category"
          :options="categoryOptions"
          clearable
          placeholder="全部"
          style="width: 130px"
        />
      </QueryBarItem>
      <QueryBarItem label="状态" label-width="50">
        <NSelect
          v-model:value="queryItems.status"
          :options="statusOptions"
          clearable
          placeholder="全部"
          style="width: 110px"
        />
      </QueryBarItem>
      <QueryBarItem label="质保" label-width="50">
        <NSelect
          v-model:value="queryItems.warranty_state"
          :options="warrantyOptions"
          clearable
          placeholder="全部"
          style="width: 130px"
        />
      </QueryBarItem>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm ref="modalFormRef" label-placement="left" label-width="90" :model="modalForm" :rules="rules">
        <NFormItem label="资产编号" path="asset_no">
          <NInput v-model:value="modalForm.asset_no" placeholder="请输入资产编号" />
        </NFormItem>
        <NFormItem label="资产名称" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入资产名称" />
        </NFormItem>
        <NFormItem label="分类" path="category">
          <NSelect v-model:value="modalForm.category" :options="categoryOptions" placeholder="请选择分类" />
        </NFormItem>
        <NFormItem label="型号" path="model">
          <NInput v-model:value="modalForm.model" placeholder="请输入型号" />
        </NFormItem>
        <NFormItem label="序列号" path="serial_no">
          <NInput v-model:value="modalForm.serial_no" placeholder="请输入序列号" />
        </NFormItem>
        <NFormItem label="采购日期" path="purchase_date">
          <NInput v-model:value="modalForm.purchase_date" placeholder="如 2026-01-01" />
        </NFormItem>
        <NFormItem label="质保到期" path="warranty_until">
          <NInput v-model:value="modalForm.warranty_until" placeholder="如 2027-01-01，可空" />
        </NFormItem>
        <NFormItem label="采购价格" path="price">
          <NInputNumber v-model:value="modalForm.price" :min="0" placeholder="元" style="width: 100%" />
        </NFormItem>
        <NFormItem label="状态" path="status">
          <NSelect v-model:value="modalForm.status" :options="statusOptions" />
        </NFormItem>
        <NFormItem label="存放位置" path="location">
          <NInput v-model:value="modalForm.location" placeholder="请输入存放位置" />
        </NFormItem>
        <NFormItem label="当前领用人" path="owner_emp_id">
          <NSelect v-model:value="modalForm.owner_emp_id" :options="employeeOptions" clearable placeholder="选择领用人（领用审批通过后自动更新）" />
        </NFormItem>
        <NFormItem label="备注" path="remark">
          <NInput v-model:value="modalForm.remark" type="textarea" placeholder="备注" />
        </NFormItem>
      </NForm>
    </CrudModal>
    <AssetQrDialog v-model:show="qrVisible" :asset="qrAsset" />
  </CommonPage>
</template>
