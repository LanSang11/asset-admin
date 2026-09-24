import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('共享抽屉展示时间字段、中文字段名、改前改后和操作人', () => {
  const drawer = read('web/src/components/business/FieldChangeDrawer.vue')
  assert.match(drawer, /include_changes:\s*true/)
  assert.match(drawer, /change_page:/)
  assert.match(drawer, /change_page_size:/)
  assert.match(drawer, /field_label/)
  assert.match(drawer, /old_value/)
  assert.match(drawer, /new_value/)
  assert.match(drawer, /operator_name/)
  assert.match(drawer, /changed_at/)
  assert.match(drawer, /暂无变更记录/)
})

test('资产和员工页面都使用共享抽屉', () => {
  for (const page of ['asset', 'employee']) {
    const source = read(`web/src/views/business/${page}/index.vue`)
    assert.match(source, /FieldChangeDrawer/)
    assert.match(source, /变更记录/)
    assert.match(source, /changeVisible/)
    assert.match(source, /openChanges/)
  }
})

test('共享抽屉在翻页失败、清空实体和初始打开时保持正确状态', () => {
  const drawer = read('web/src/components/business/FieldChangeDrawer.vue')

  assert.doesNotMatch(drawer, /v-model:page/)
  assert.match(drawer, /\n\s*:page="page"/)
  assert.match(drawer, /function clearChanges\(\) \{[^}]*loading\.value = false/)
  assert.match(drawer, /if \(!entityId\) \{\s+clearChanges\(\)/)
  assert.match(drawer, /\},\s*\{ immediate: true \}\s*\)/)
  assert.doesNotMatch(drawer, /<NDrawerContent[^>]*@close=/)
})
