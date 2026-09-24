import test from 'node:test'
import assert from 'node:assert/strict'
import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

function walkVue(dir) {
  const out = []
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name)
    if (entry.isDirectory()) out.push(...walkVue(full))
    else if (entry.name.endsWith('.vue')) out.push(full)
  }
  return out
}

const crudTable = read('web/src/components/table/CrudTable.vue')
const assetPage = read('web/src/views/business/asset/index.vue')
const employeePage = read('web/src/views/business/employee/index.vue')
const workMyAssets = read('web/src/views/work/my-assets/index.vue')
const allowedSettingPages = new Set([
  'web/src/views/business/asset/index.vue',
  'web/src/views/business/employee/index.vue',
])

test('CrudTable 列设置默认关闭，只改前端列，偏好走 localStorage', () => {
  assert.match(crudTable, /columnSetting:\s*\{\s*type:\s*Boolean,\s*default:\s*false/)
  assert.match(crudTable, /tableId:/)
  assert.match(crudTable, /lockedColumnKeys:/)
  assert.match(crudTable, /列设置/)
  assert.match(crudTable, /恢复默认列/)
  assert.match(crudTable, /from '@\/utils\/table-column-prefs'/)
  assert.match(crudTable, /getColumnPrefStorage/)
  assert.match(crudTable, /:columns="visibleColumns"/)
  assert.doesNotMatch(crudTable, /from ['"]@\/api['"]/)
  assert.doesNotMatch(crudTable, /sessionStorage/)
})

test('仅管理员资产表和员工表打开列设置，并锁定编号/名称/操作', () => {
  assert.match(assetPage, /column-setting/)
  assert.match(assetPage, /table-id="admin-asset"/)
  assert.match(assetPage, /:locked-column-keys="\['asset_no', 'name', 'actions'\]"/)
  assert.match(employeePage, /column-setting/)
  assert.match(employeePage, /table-id="admin-employee"/)
  assert.match(employeePage, /:locked-column-keys="\['emp_no', 'name', 'actions'\]"/)
  assert.doesNotMatch(workMyAssets, /column-setting/)
  assert.doesNotMatch(workMyAssets, /列设置/)
})

test('其它 CrudTable 页面不得打开列设置', () => {
  const vueRoot = resolve(repoRoot, 'web/src')
  const offenders = []
  for (const file of walkVue(vueRoot)) {
    const rel = relative(repoRoot, file).replaceAll('\\', '/')
    if (allowedSettingPages.has(rel)) continue
    const source = readFileSync(file, 'utf8')
    if (!source.includes('<CrudTable')) continue
    if (
      /column-setting/.test(source) ||
      /columnSetting\s*=/.test(source) ||
      /table-id=/.test(source) ||
      /locked-column-keys/.test(source)
    ) {
      offenders.push(rel)
    }
  }
  assert.deepEqual(offenders, [])
})

test('导出口径不绑定当前显示列', () => {
  assert.match(assetPage, /downloadFile\(\s*'\/export\/assets'/)
  assert.match(assetPage, /'资产数据\.csv'/)
  assert.match(employeePage, /downloadFile\(\s*'\/export\/employees'/)
  assert.match(employeePage, /'员工数据\.csv'/)
  assert.doesNotMatch(assetPage, /visibleColumns|hiddenKeys|localStorage/)
  assert.doesNotMatch(employeePage, /visibleColumns|hiddenKeys|localStorage/)
})
