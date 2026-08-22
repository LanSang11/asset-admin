<script setup>
import { h, onMounted, ref, resolveDirective, withDirectives } from 'vue'
import {
  NButton,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NModal,
  NPopconfirm,
  NSelect,
  NSwitch,
  NUpload,
} from 'naive-ui'

import CommonPage from '@/components/page/CommonPage.vue'
import QueryBarItem from '@/components/query-bar/QueryBarItem.vue'
import CrudModal from '@/components/table/CrudModal.vue'
import CrudTable from '@/components/table/CrudTable.vue'

import { useCRUD } from '@/composables'
import api from '@/api'
import { downloadFile } from '@/utils/download'

defineOptions({ name: '员工管理' })

const $table = ref(null)
const queryItems = ref({ status: -1, sort_by: 'created_at', sort_order: 'desc' })
const vPermission = resolveDirective('permission')

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
  name: '员工',
  initForm: { gender: 0, position: '', phone: '', email: '', is_manager: false, status: true },
  doCreate: api.createEmployee,
  doUpdate: api.updateEmployee,
  doDelete: api.deleteEmployee,
  stepUpDeleteKey: 'employee_delete',
  refresh: () => $table.value?.handleSearch(),
})

const deptOptions = ref([])
const userOptions = ref([])
const statusOptions = [
  { label: '全部', value: -1 },
  { label: '在职', value: 1 },
  { label: '离职', value: 0 },
]
const sortFieldOptions = [
  { label: '创建时间', value: 'created_at' },
  { label: '工号', value: 'emp_no' },
  { label: '姓名', value: 'name' },
  { label: '入职日期', value: 'hire_date' },
]
const sortOrderOptions = [
  { label: '降序', value: 'desc' },
  { label: '升序', value: 'asc' },
]
const attachVisible = ref(false)
const attachEmp = ref(null)
const attachRows = ref([])
const attachLoading = ref(false)

async function openAttach(row) {
  attachEmp.value = row
  attachVisible.value = true
  await loadAttach()
}

async function loadAttach() {
  if (!attachEmp.value) return
  attachLoading.value = true
  try {
    const res = await api.getEmployeeAttachments({ employee_id: attachEmp.value.id })
    attachRows.value = res.data?.list || []
  } finally {
    attachLoading.value = false
  }
}

async function onAttachUpload({ file, onFinish, onError }) {
  const raw = file?.file
  if (!raw || !attachEmp.value) {
    onError && onError()
    return
  }
  const fd = new FormData()
  fd.append('employee_id', String(attachEmp.value.id))
  fd.append('file', raw)
  try {
    await api.uploadEmployeeAttachment(fd)
    $message.success('附件已上传')
    await loadAttach()
    onFinish && onFinish()
  } catch (e) {
    $message.error(e?.message || e?.msg || '上传失败')
    onError && onError()
  }
}

function downloadAttach(row) {
  downloadFile(`/employee-attachment/download?id=${row.id}`, {}, row.original_name || 'attachment')
}

async function deleteAttach(row) {
  await api.deleteEmployeeAttachment({ id: row.id })
  $message.success('已删除')
  await loadAttach()
}

onMounted(() => {
  $table.value?.handleSearch()
  api.getDepts().then((res) => {
    deptOptions.value = (res.data || []).map((d) => ({ label: d.name, value: d.id }))
  })
  api.getUserList({ page: 1, page_size: 100 }).then((res) => {
    userOptions.value = (res.data?.list || []).map((u) => ({ label: `${u.username}`, value: u.id }))
  })
})

const rules = {
  emp_no: [{ required: true, message: '请输入工号', trigger: ['input', 'blur'] }],
  name: [{ required: true, message: '请输入姓名', trigger: ['input', 'blur'] }],
}

const genderOptions = [
  { label: '未知', value: 0 },
  { label: '男', value: 1 },
  { label: '女', value: 2 },
]

const columns = [
  { title: '工号', key: 'emp_no', width: 110, align: 'center' },
  { title: '姓名', key: 'name', width: 100, align: 'center' },
  {
    title: '性别',
    key: 'gender',
    width: 70,
    align: 'center',
    render: (row) => (row.gender === 1 ? '男' : row.gender === 2 ? '女' : '未知'),
  },
  {
    title: '部门',
    key: 'dept_id',
    width: 110,
    align: 'center',
    render: (row) => deptOptions.value.find((d) => d.value === row.dept_id)?.label || '-',
  },
  { title: '职位', key: 'position', width: 120, align: 'center', ellipsis: { tooltip: true } },
  { title: '手机', key: 'phone', width: 130, align: 'center' },
  { title: '邮箱', key: 'email', width: 180, align: 'center', ellipsis: { tooltip: true } },
  {
    title: '入职日期',
    key: 'hire_date',
    width: 110,
    align: 'center',
    render: (row) => row.hire_date || '-',
  },
  {
    title: '部门主管',
    key: 'is_manager',
    width: 90,
    align: 'center',
    render: (row) => (row.is_manager ? '是' : '否'),
  },
  {
    title: '状态',
    key: 'status',
    width: 80,
    align: 'center',
    render: (row) => (row.status ? '在职' : '离职'),
  },
  {
    title: '操作',
    key: 'actions',
    width: 210,
    align: 'center',
    render: (row) => [
      withDirectives(
        h(
          NButton,
          {
            size: 'small',
            onClick: () => openAttach(row),
          },
          { default: () => '附件' }
        ),
        [[vPermission, 'get/api/v1/employee-attachment/list']]
      ),
      // 修复：按钮加 v-permission（无权限不渲染，而非点击后被 403）
      withDirectives(
        h(
          NButton,
          {
            size: 'small',
            type: 'primary',
            onClick: () => handleEdit(row),
          },
          { default: () => '编辑' }
        ),
        [[vPermission, 'post/api/v1/employee/update']]
      ),
      h(
        NPopconfirm,
        {
          onPositiveClick: () => handleDelete({ employee_id: row.id }),
        },
        {
          trigger: () =>
            withDirectives(
              h(
                NButton,
                { size: 'small', type: 'error', style: 'margin-left:8px' },
                { default: () => '删除' }
              ),
              [[vPermission, 'delete/api/v1/employee/delete']]
            ),
          default: () => `确定删除员工「${row.name}」吗？`,
        }
      ),
    ],
  },
]

function addEmployee() {
  modalForm.value = {
    gender: 0,
    position: '',
    phone: '',
    email: '',
    is_manager: false,
    status: true,
  }
  handleAdd()
}

function handleExport() {
  downloadFile(
    '/export/employees',
    {
      keyword: queryItems.value.keyword || '',
      dept_id: queryItems.value.dept_id || 0,
      status: queryItems.value.status ?? -1,
      sort_by: queryItems.value.sort_by || 'created_at',
      sort_order: queryItems.value.sort_order || 'desc',
    },
    '员工数据.csv',
    'export_employees'
  )
}
</script>

<template>
  <CommonPage>
    <template #action>
      <NButton
        v-permission="'get/api/v1/export/employees'"
        style="margin-right: 8px"
        @click="handleExport"
        >导出 CSV</NButton
      >
      <NButton v-permission="'post/api/v1/employee/create'" type="primary" @click="addEmployee"
        >新增员工</NButton
      >
    </template>
    <CrudTable
      ref="$table"
      v-model:query-items="queryItems"
      :columns="columns"
      :get-data="api.getEmployeeList"
    >
      <template #queryBar>
        <QueryBarItem label="关键词" label-width="60">
          <NInput
            v-model:value="queryItems.keyword"
            type="text"
            clearable
            placeholder="姓名/工号/手机"
            style="width: 180px"
            @keydown.enter="$table?.handleSearch()"
          />
        </QueryBarItem>
        <QueryBarItem label="部门" label-width="50">
          <NSelect
            v-model:value="queryItems.dept_id"
            :options="deptOptions"
            clearable
            placeholder="全部"
            style="width: 140px"
          />
        </QueryBarItem>
        <QueryBarItem label="状态" label-width="50">
          <NSelect
            v-model:value="queryItems.status"
            :options="statusOptions"
            placeholder="全部"
            style="width: 110px"
          />
        </QueryBarItem>
        <QueryBarItem label="排序" label-width="50">
          <NSelect
            v-model:value="queryItems.sort_by"
            :options="sortFieldOptions"
            style="width: 120px"
          />
        </QueryBarItem>
        <QueryBarItem label="顺序" label-width="50">
          <NSelect
            v-model:value="queryItems.sort_order"
            :options="sortOrderOptions"
            style="width: 100px"
          />
        </QueryBarItem>
      </template>
    </CrudTable>

    <CrudModal
      v-model:visible="modalVisible"
      :title="modalTitle"
      :loading="modalLoading"
      @save="handleSave"
    >
      <NForm
        ref="modalFormRef"
        label-placement="left"
        label-width="90"
        :model="modalForm"
        :rules="rules"
      >
        <NFormItem label="工号" path="emp_no">
          <NInput v-model:value="modalForm.emp_no" placeholder="请输入工号" />
        </NFormItem>
        <NFormItem label="姓名" path="name">
          <NInput v-model:value="modalForm.name" placeholder="请输入姓名" />
        </NFormItem>
        <NFormItem label="性别" path="gender">
          <NSelect v-model:value="modalForm.gender" :options="genderOptions" />
        </NFormItem>
        <NFormItem label="部门" path="dept_id">
          <NSelect
            v-model:value="modalForm.dept_id"
            :options="deptOptions"
            clearable
            placeholder="请选择部门"
          />
        </NFormItem>
        <NFormItem label="职位" path="position">
          <NInput v-model:value="modalForm.position" placeholder="请输入职位" />
        </NFormItem>
        <NFormItem label="入职日期" path="hire_date">
          <NInput v-model:value="modalForm.hire_date" placeholder="如 2026-01-01" />
        </NFormItem>
        <NFormItem label="手机" path="phone">
          <NInput v-model:value="modalForm.phone" placeholder="请输入手机号" />
        </NFormItem>
        <NFormItem label="邮箱" path="email">
          <NInput v-model:value="modalForm.email" placeholder="请输入邮箱" />
        </NFormItem>
        <NFormItem label="绑定账号" path="user_id">
          <NSelect
            v-model:value="modalForm.user_id"
            :options="userOptions"
            clearable
            placeholder="选择登录账号（一人一号）"
          />
        </NFormItem>
        <NFormItem label="部门主管" path="is_manager">
          <NSwitch v-model:value="modalForm.is_manager" />
        </NFormItem>
        <NFormItem label="状态" path="status">
          <NSwitch
            v-model:value="modalForm.status"
            :checked-value="true"
            :unchecked-value="false"
          />
        </NFormItem>
      </NForm>
    </CrudModal>
    <NModal v-model:show="attachVisible" preset="card" title="员工附件" style="width: 520px">
      <p v-if="attachEmp" style="margin-bottom: 8px">{{ attachEmp.emp_no }} {{ attachEmp.name }}</p>
      <NUpload :show-file-list="false" :custom-request="onAttachUpload">
        <NButton type="primary" size="small">上传</NButton>
      </NUpload>
      <ul style="margin-top: 12px">
        <li v-for="row in attachRows" :key="row.id" style="margin-bottom: 6px">
          {{ row.original_name }}（{{ row.size }} 字节）
          <NButton size="tiny" @click="downloadAttach(row)">下载</NButton>
          <NButton size="tiny" type="error" style="margin-left: 6px" @click="deleteAttach(row)"
            >删除</NButton
          >
        </li>
        <li v-if="!attachLoading && !attachRows.length">暂无附件</li>
      </ul>
    </NModal>
  </CommonPage>
</template>
