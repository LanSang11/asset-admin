import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('管理员首页与统计看板拆成资产运营和安全态势', () => {
  const workbench = read('web/src/views/workbench/index.vue')
  const dashboard = read('web/src/views/business/dashboard/index.vue')
  const home = read('web/src/views/work/home/index.vue')

  for (const source of [workbench, dashboard]) {
    assert.match(source, /资产运营/)
    assert.match(source, /安全态势/)
    assert.match(source, /isSuperUser/)
    assert.match(source, /getSecurityPosture/)
    assert.match(source, /SecurityPostureSection/)
    assert.match(source, /\/system\/security/)
  }
  assert.doesNotMatch(home, /安全态势/)
  assert.doesNotMatch(home, /getSecurityPosture/)
})

test('态势组件可下钻且不直接调接口', () => {
  const section = read('web/src/components/dashboard/SecurityPostureSection.vue')
  const model = read('web/src/views/dashboard-model.js')

  assert.doesNotMatch(section, /@\/api|use[A-Z]\w*Store|v-html/)
  assert.match(section, /emit\(['"]drill['"]/)
  assert.match(section, /认证失败|login_failure/)
  assert.match(model, /normalizeSecurityPosture/)
  assert.match(model, /buildSecurityDrillQuery/)
})

test('安全中心吃下钻 FilterSpec 并展示攻击聚合页', () => {
  const page = read('web/src/views/system/security/index.vue')
  assert.match(page, /route\.query/)
  assert.match(page, /name="attacks"/)
  assert.match(page, /getAttackAgg/)
  assert.match(page, /applyRouteFilter|start_time/)
})
