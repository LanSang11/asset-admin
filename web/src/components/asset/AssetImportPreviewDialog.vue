<template>
  <NModal
    :show="show"
    preset="card"
    title="资产导入预览"
    class="asset-import-preview"
    :closable="!loading"
    :close-on-esc="!loading"
    :mask-closable="!loading"
    @update:show="onShow"
  >
    <NAlert type="warning" :bordered="false">
      当前只是预检，尚未写入数据库。确认后仍需完成二次验证；重复编号继续跳过。
    </NAlert>

    <div class="asset-import-preview__summary">
      <NTag type="success">可导入 {{ preview.ok || 0 }}</NTag>
      <NTag type="warning">跳过 {{ preview.skipped || 0 }}</NTag>
      <NTag type="error">错误 {{ preview.errors || 0 }}</NTag>
      <span>共读取 {{ preview.total || 0 }} 行</span>
    </div>

    <div v-if="mappings.length" class="asset-import-preview__mappings">
      <strong>已应用列映射：</strong>
      <span v-for="item in mappings" :key="`${item.source}-${item.target}`">
        {{ item.source }} → {{ item.target }}
      </span>
    </div>

    <NDataTable
      :columns="columns"
      :data="rows"
      :pagination="pagination"
      :max-height="420"
      :row-key="rowKey"
      size="small"
      striped
    />

    <template #footer>
      <div class="asset-import-preview__footer">
        <NButton :disabled="loading" @click="onShow(false)">取消</NButton>
        <div class="asset-import-preview__actions">
          <NButton v-if="preview.errors" type="error" secondary @click="$emit('download-errors')">
            下载失败行 CSV
          </NButton>
          <NButton
            type="primary"
            :loading="loading"
            :disabled="!commitAllowed"
            @click="$emit('confirm')"
          >
            确认导入 {{ preview.ok || 0 }} 条
          </NButton>
        </div>
      </div>
    </template>
  </NModal>
</template>

<script setup>
import { computed, h } from 'vue'
import { NAlert, NButton, NDataTable, NModal, NTag } from 'naive-ui'
import {
  buildAssetImportPreviewRows,
  canCloseAssetImport,
  canCommitAssetImport,
} from '@/utils/asset-import'

const props = defineProps({
  show: { type: Boolean, default: false },
  preview: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
})
const emit = defineEmits(['update:show', 'cancel', 'confirm', 'download-errors'])

const rows = computed(() => buildAssetImportPreviewRows(props.preview))
const mappings = computed(() => props.preview.header_mappings || [])
const commitAllowed = computed(() => canCommitAssetImport(props.preview) && !props.loading)
const pagination = { pageSize: 10 }
const outcomeTypes = { 可导入: 'success', 跳过: 'warning', 错误: 'error' }

const columns = [
  { title: '行号', key: 'line', width: 70, align: 'center' },
  { title: '资产编号', key: 'asset_no', width: 130, ellipsis: { tooltip: true } },
  { title: '名称', key: 'name', width: 150, ellipsis: { tooltip: true } },
  {
    title: '结果',
    key: 'outcome',
    width: 90,
    align: 'center',
    render: (row) => h(NTag, { size: 'small', type: outcomeTypes[row.outcome] }, () => row.outcome),
  },
  { title: '说明', key: 'reason', minWidth: 220, ellipsis: { tooltip: true } },
]

function rowKey(row) {
  return `${row.line}-${row.outcome}-${row.asset_no}`
}

function onShow(value) {
  if (!value && !canCloseAssetImport(props.loading)) return
  emit('update:show', value)
  if (!value) emit('cancel')
}
</script>

<style scoped>
:global(.asset-import-preview) {
  width: min(920px, 94vw);
}

.asset-import-preview__summary {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 14px 0;
}

.asset-import-preview__summary span:last-child {
  color: var(--n-text-color);
  opacity: 0.72;
}

.asset-import-preview__mappings {
  display: flex;
  flex-wrap: wrap;
  gap: 6px 12px;
  margin: 0 0 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: rgba(24, 160, 88, 0.08);
  font-size: 13px;
}

.asset-import-preview__footer,
.asset-import-preview__actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

@media (max-width: 640px) {
  .asset-import-preview__footer {
    align-items: stretch;
    flex-direction: column-reverse;
  }

  .asset-import-preview__actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
