import test from 'node:test'
import assert from 'node:assert/strict'

const prefs = await import('../../../web/src/utils/table-column-prefs.js')

function memoryStorage() {
  const map = new Map()
  return {
    getItem: (key) => (map.has(key) ? map.get(key) : null),
    setItem: (key, value) => {
      map.set(key, String(value))
    },
    removeItem: (key) => {
      map.delete(key)
    },
  }
}

const columns = [
  { title: '资产编号', key: 'asset_no', width: 110 },
  { title: '资产名称', key: 'name', width: 140 },
  { title: '价格(元)', key: 'price', width: 100 },
  { title: '状态', key: 'status', width: 80 },
  { type: 'selection' },
  { title: '操作', key: 'actions', width: 210 },
]
const locked = ['asset_no', 'name', 'actions']

test('列偏好键按用户、路由和表隔离，缺用户不落盘', () => {
  assert.equal(
    prefs.buildTableColumnPrefKey({ userId: 1, routePath: '/asset/', tableId: 'admin-asset' }),
    'tbl-col:1:/asset:admin-asset',
  )
  assert.equal(
    prefs.buildTableColumnPrefKey({ userId: 2, routePath: '/asset', tableId: 'admin-asset' }),
    'tbl-col:2:/asset:admin-asset',
  )
  assert.equal(
    prefs.buildTableColumnPrefKey({ userId: 1, routePath: '/employee', tableId: 'admin-employee' }),
    'tbl-col:1:/employee:admin-employee',
  )
  assert.equal(prefs.buildTableColumnPrefKey({ userId: '', routePath: '/asset', tableId: 'admin-asset' }), null)
  assert.equal(prefs.buildTableColumnPrefKey({ routePath: '/asset', tableId: 'admin-asset' }), null)
})

test('列设置清单跳过无标题和 selection 列，锁定列不可藏', () => {
  assert.deepEqual(prefs.listSettingColumns(columns, locked), [
    { key: 'asset_no', title: '资产编号', locked: true },
    { key: 'name', title: '资产名称', locked: true },
    { key: 'price', title: '价格(元)', locked: false },
    { key: 'status', title: '状态', locked: false },
    { key: 'actions', title: '操作', locked: true },
  ])
})

test('sanitize 丢掉锁定列、未知列和脏数据', () => {
  assert.deepEqual(
    prefs.sanitizeHiddenKeys(['price', 'actions', 'secret', '', 'price'], columns, locked),
    ['price'],
  )
})

test('隐藏价格后刷新仍隐藏，锁定列即使被写入存储也继续显示', () => {
  const original = [...columns]
  const visible = prefs.filterVisibleColumns(columns, ['price', 'actions', 'secret'], locked)
  assert.deepEqual(
    visible.map((column) => column.key || column.type),
    ['asset_no', 'name', 'status', 'selection', 'actions'],
  )
  assert.equal(visible.includes(columns[2]), false)
  assert.deepEqual(columns, original)
})

test('切换显隐忽略锁定列，恢复默认会清空存储', () => {
  const afterHide = prefs.applyColumnVisibility([], 'price', false, locked)
  assert.deepEqual(afterHide, ['price'])
  assert.deepEqual(prefs.applyColumnVisibility(afterHide, 'price', true, locked), [])
  assert.deepEqual(prefs.applyColumnVisibility(['price'], 'actions', false, locked), ['price'])

  const storage = memoryStorage()
  const key = prefs.buildTableColumnPrefKey({ userId: 7, routePath: '/asset', tableId: 'admin-asset' })
  assert.equal(prefs.writeHiddenKeys(storage, key, ['price']), true)
  assert.deepEqual(prefs.readHiddenKeys(storage, key), ['price'])
  assert.equal(prefs.writeHiddenKeys(storage, key, []), true)
  assert.equal(storage.getItem(key), null)
  assert.deepEqual(prefs.readHiddenKeys(storage, key), [])
})

test('损坏的 localStorage JSON 视为无偏好，缺键不读写', () => {
  const storage = memoryStorage()
  storage.setItem('tbl-col:1:/asset:admin-asset', '{not json')
  assert.deepEqual(prefs.readHiddenKeys(storage, 'tbl-col:1:/asset:admin-asset'), [])
  assert.deepEqual(prefs.readHiddenKeys(storage, null), [])
  assert.equal(prefs.writeHiddenKeys(storage, null, ['price']), false)
})
