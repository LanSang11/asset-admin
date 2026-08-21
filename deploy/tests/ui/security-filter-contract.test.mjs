import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const page = readFileSync(resolve(repoRoot, 'web/src/views/system/security/index.vue'), 'utf8')

test('安全中心登录日志提交成功状态、时间段和地区排除', () => {
  assert.match(page, /exclude_region/)
  assert.match(page, /unknown_region/)
  assert.match(page, /start_time/)
  assert.match(page, /end_time/)
  assert.match(page, /NDatePicker/)
  assert.match(page, /地区不是/)
  assert.match(page, /仅成功/)
  assert.match(page, /未知地区会单独留下来/)
})
