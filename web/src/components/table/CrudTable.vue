<template>
  <div v-bind="$attrs">
    <QueryBar v-if="$slots.queryBar" mb-30 @search="handleSearch" @reset="handleReset">
      <slot name="queryBar" />
    </QueryBar>

    <div v-if="columnSetting" class="crud-table__toolbar">
      <n-popover trigger="click" placement="bottom-end">
        <template #trigger>
          <n-button size="small" aria-label="列设置">列设置</n-button>
        </template>
        <div class="crud-table__column-panel">
          <n-checkbox
            v-for="item in settingColumns"
            :key="item.key"
            :checked="isColumnChecked(item.key)"
            :disabled="item.locked"
            @update:checked="(checked) => onToggleColumn(item.key, checked)"
          >
            {{ item.title }}
          </n-checkbox>
          <n-button
            class="crud-table__column-reset"
            size="small"
            tertiary
            @click="resetColumnSetting"
          >
            恢复默认列
          </n-button>
        </div>
      </n-popover>
    </div>

    <n-data-table
      :remote="remote"
      :loading="loading"
      :columns="visibleColumns"
      :data="tableData"
      :scroll-x="scrollX"
      :row-key="(row) => row[rowKey]"
      :pagination="isPagination ? pagination : false"
      @update:checked-row-keys="onChecked"
      @update:page="onPageChange"
    />
  </div>
</template>

<script setup>
import { useUserStore } from '@/store'
import {
  applyColumnVisibility,
  buildTableColumnPrefKey,
  filterVisibleColumns,
  getColumnPrefStorage,
  listSettingColumns,
  readHiddenKeys,
  sanitizeHiddenKeys,
  writeHiddenKeys,
} from '@/utils/table-column-prefs'

const props = defineProps({
  /**
   * @remote true: 后端分页  false： 前端分页
   */
  remote: {
    type: Boolean,
    default: true,
  },
  /**
   * @remote 是否分页
   */
  isPagination: {
    type: Boolean,
    default: true,
  },
  scrollX: {
    type: Number,
    default: 450,
  },
  rowKey: {
    type: String,
    default: 'id',
  },
  columns: {
    type: Array,
    required: true,
  },
  /**
   * 默认关闭。需要列显隐的页面显式传入 column-setting。
   */
  columnSetting: {
    type: Boolean,
    default: false,
  },
  tableId: {
    type: String,
    default: 'default',
  },
  lockedColumnKeys: {
    type: Array,
    default() {
      return ['actions']
    },
  },
  /** queryBar中的参数 */
  queryItems: {
    type: Object,
    default() {
      return {}
    },
  },
  /** 补充参数（可选） */
  extraParams: {
    type: Object,
    default() {
      return {}
    },
  },
  /**
   * ! 约定接口入参出参
   * * 分页模式需约定分页接口入参
   *    @page_size 分页参数：一页展示多少条，默认10
   *    @page   分页参数：页码，默认1
   */
  getData: {
    type: Function,
    required: true,
  },
})

const emit = defineEmits(['update:queryItems', 'onChecked', 'onDataChange'])
const userStore = useUserStore()
const route = useRoute()
const loading = ref(false)
const initQuery = { ...props.queryItems }
const tableData = ref([])
const hiddenKeys = ref([])
const prefKey = computed(() =>
  buildTableColumnPrefKey({
    userId: userStore.userId,
    routePath: route.path,
    tableId: props.tableId,
  })
)
const settingColumns = computed(() => listSettingColumns(props.columns, props.lockedColumnKeys))
const visibleColumns = computed(() => {
  if (!props.columnSetting) return props.columns
  return filterVisibleColumns(props.columns, hiddenKeys.value, props.lockedColumnKeys)
})

function reloadColumnPrefs() {
  if (!props.columnSetting) {
    hiddenKeys.value = []
    return
  }
  const storage = getColumnPrefStorage()
  const stored = readHiddenKeys(storage, prefKey.value)
  const clean = sanitizeHiddenKeys(stored, props.columns, props.lockedColumnKeys)
  hiddenKeys.value = clean
  if (JSON.stringify(stored) !== JSON.stringify(clean)) {
    writeHiddenKeys(storage, prefKey.value, clean)
  }
}

function persistHiddenKeys() {
  if (!props.columnSetting) return
  writeHiddenKeys(getColumnPrefStorage(), prefKey.value, hiddenKeys.value)
}

function isColumnChecked(key) {
  if ((props.lockedColumnKeys || []).includes(key)) return true
  return !hiddenKeys.value.includes(key)
}

function onToggleColumn(key, visible) {
  hiddenKeys.value = applyColumnVisibility(hiddenKeys.value, key, visible, props.lockedColumnKeys)
  persistHiddenKeys()
}

function resetColumnSetting() {
  hiddenKeys.value = []
  persistHiddenKeys()
}

watch(
  () => [props.columnSetting, prefKey.value],
  () => reloadColumnPrefs(),
  { immediate: true }
)
const pagination = reactive({
  page: 1,
  page_size: 10,
  pageSizes: [10, 20, 50, 100],
  showSizePicker: true,
  prefix({ itemCount }) {
    return `共 ${itemCount} 条`
  },
  onChange: (page) => {
    pagination.page = page
  },
  onUpdatePageSize: (pageSize) => {
    pagination.page_size = pageSize
    pagination.page = 1
    handleQuery()
  },
})

async function handleQuery() {
  try {
    loading.value = true
    let paginationParams = {}
    // 如果非分页模式或者使用前端分页,则无需传分页参数
    if (props.isPagination && props.remote) {
      paginationParams = { page: pagination.page, page_size: pagination.page_size }
    }
    const resp = await props.getData({
      ...props.queryItems,
      ...props.extraParams,
      ...paginationParams,
    })
    // 修复：兼容两种后端返回契约（SuccessExtra 平铺 {data,total} 与 Success 嵌套 {data:{list,total}}）
    let list = resp?.data
    let total = resp?.total
    if (list && !Array.isArray(list) && Array.isArray(list.list)) {
      total = list.total ?? total
      list = list.list
    }
    tableData.value = Array.isArray(list) ? list : []
    pagination.itemCount = total || 0
  } catch (error) {
    tableData.value = []
    pagination.itemCount = 0
  } finally {
    emit('onDataChange', tableData.value)
    loading.value = false
  }
}
function handleSearch() {
  pagination.page = 1
  handleQuery()
}
async function handleReset() {
  const queryItems = { ...props.queryItems }
  for (const key in queryItems) {
    queryItems[key] = null
  }
  emit('update:queryItems', { ...queryItems, ...initQuery })
  await nextTick()
  pagination.page = 1
  handleQuery()
}
function onPageChange(currentPage) {
  pagination.page = currentPage
  if (props.remote) {
    handleQuery()
  }
}
function onChecked(rowKeys) {
  if (props.columns.some((item) => item.type === 'selection')) {
    emit('onChecked', rowKeys)
  }
}

defineExpose({
  handleSearch,
  handleReset,
  tableData,
})
</script>

<style scoped>
.crud-table__toolbar {
  display: flex;
  justify-content: flex-end;
  margin: 0 0 12px;
}
.crud-table__column-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 168px;
}
.crud-table__column-reset {
  margin-top: 4px;
  align-self: flex-start;
}
</style>
