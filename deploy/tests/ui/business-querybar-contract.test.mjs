import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

const businessPages = [
  'employee',
  'asset',
  'asset-use',
  'approval',
  'transfer',
  'repair',
  'inventory',
]

test('业务列表筛选项必须放进 CrudTable 的 queryBar 命名插槽', () => {
  for (const pageName of businessPages) {
    const source = read(`web/src/views/business/${pageName}/index.vue`)
    const itemCount = (source.match(/<QueryBarItem\b/g) || []).length
    const slotCount = (source.match(/<template\s+#queryBar>/g) || []).length

    assert.ok(itemCount > 0, `${pageName} 应包含筛选项`)
    assert.equal(
      slotCount,
      pageName === 'inventory' ? 2 : 1,
      `${pageName} 的每个筛选表格都应声明 queryBar 插槽`,
    )
    assert.doesNotMatch(
      source,
      /<CrudTable\b[^>]*>\s*<QueryBarItem\b/s,
      `${pageName} 仍把筛选项放在默认插槽`,
    )
  }
})

test('员工页面展示状态与安全排序，并把同一组条件传给导出', () => {
  const employee = read('web/src/views/business/employee/index.vue')

  assert.match(employee, /queryItems\.status/)
  assert.match(employee, /queryItems\.sort_by/)
  assert.match(employee, /queryItems\.sort_order/)
  assert.match(employee, /keyword:\s*queryItems\.value\.keyword/)
  assert.match(employee, /dept_id:\s*queryItems\.value\.dept_id/)
  assert.match(employee, /status:\s*queryItems\.value\.status/)
  assert.match(employee, /sort_by:\s*queryItems\.value\.sort_by/)
  assert.match(employee, /sort_order:\s*queryItems\.value\.sort_order/)
})
