<script setup>
import { onMounted, ref } from 'vue'
import { NButton, NUpload } from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { downloadFile } from '@/utils/download'

defineOptions({ name: '我的附件' })

const rows = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await api.getEmployeeAttachments({})
    rows.value = res.data?.list || []
  } finally {
    loading.value = false
  }
}

async function onUpload({ file, onFinish, onError }) {
  const raw = file?.file
  if (!raw) {
    onError && onError()
    return
  }
  const fd = new FormData()
  fd.append('file', raw)
  try {
    await api.uploadEmployeeAttachment(fd)
    $message.success('附件已上传')
    await load()
    onFinish && onFinish()
  } catch (e) {
    $message.error(e?.message || e?.msg || '上传失败')
    onError && onError()
  }
}

function download(row) {
  downloadFile(`/employee-attachment/download?id=${row.id}`, {}, row.original_name || 'attachment')
}

async function remove(row) {
  await api.deleteEmployeeAttachment({ id: row.id })
  $message.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <CommonPage title="我的附件">
    <NUpload :show-file-list="false" :custom-request="onUpload">
      <NButton type="primary">上传附件</NButton>
    </NUpload>
    <p style="margin-top: 8px; color: #888">仅限 pdf / 图片 / Office / txt，最大 5MB。下载需登录。</p>
    <ul style="margin-top: 12px">
      <li v-for="row in rows" :key="row.id" style="margin-bottom: 8px">
        {{ row.original_name }}（{{ row.size }} 字节）
        <NButton size="tiny" @click="download(row)">下载</NButton>
        <NButton size="tiny" type="error" style="margin-left: 6px" @click="remove(row)">删除</NButton>
      </li>
      <li v-if="!loading && !rows.length">还没有附件</li>
    </ul>
  </CommonPage>
</template>
