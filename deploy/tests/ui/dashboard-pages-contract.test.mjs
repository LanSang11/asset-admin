import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('管理员首页消费真实统计并使用方案 2 共享组件', () => {
  const source = read('web/src/views/workbench/index.vue')

  for (const token of ['getDashboardStats', 'normalizeDashboardStats', 'buildDashboardMetrics', 'MetricCard', 'DashboardPanel', 'TrendBars']) {
    assert.match(source, new RegExp(token))
  }
  assert.doesNotMatch(source, /dummyText|v-html|logout\(/)
  assert.match(source, /catch[\s\S]*dashboardError/)
})

test('管理员首页快捷入口由已授权管理菜单过滤', () => {
  const source = read('web/src/views/workbench/index.vue')

  for (const token of ['usePermissionStore', 'permissionStore.menus', 'buildAdminMenuModels', 'collectMenuPaths']) {
    assert.match(source, new RegExp(token))
  }
  assert.match(source, /quickActions\s*=\s*computed\(/)
  assert.match(source, /filter\([\s\S]*availableMenuPaths/)
})

test('管理员首页主操作按资产菜单授权并导向既有新增资产入口', () => {
  const workbench = read('web/src/views/workbench/index.vue')
  const assetPage = read('web/src/views/business/asset/index.vue')

  assert.match(workbench, /canCreateAsset\s*=\s*computed\([\s\S]*availableMenuPaths/)
  assert.match(workbench, /新增资产/)
  assert.match(workbench, /router\.push\(['"]\/business\/asset['"]\)/)
  assert.match(assetPage, /@click=['"]addAsset['"]/)
})

test('工作台首页保留 API 能力显隐且无系统管理入口', () => {
  const source = read('web/src/views/work/home/index.vue')

  assert.match(source, /function hasApi/)
  assert.match(source, /post\/api\/v1\/asset-use\/approve/)
  assert.match(source, /buildDashboardMetrics/)
  assert.match(source, /MetricCard/)
  assert.match(source, /DashboardPanel/)
  assert.doesNotMatch(source, /\/system\/|系统管理|v-html/)
  assert.match(source, /status:\s*1/)
  assert.match(source, /status:\s*2/)
  assert.match(source, /getMyInFlightAssetUseCount/)
  for (const match of source.matchAll(/page_size:\s*(\d+)/g)) assert.ok(Number(match[1]) <= 100)
})

test('统计看板以收紧后的 scope 控制排行并复用趋势组件', () => {
  const source = read('web/src/views/business/dashboard/index.vue')

  for (const token of ['normalizeDashboardStats', 'buildDashboardMetrics', 'getDashboardScopeCopy', 'MetricCard', 'DashboardPanel', 'TrendBars']) {
    assert.match(source, new RegExp(token))
  }
  assert.match(source, /scope(?:\.value)?\s*!==\s*['"]self['"]/)
  assert.doesNotMatch(source, /maxTrend\s*\(|v-html|logout\(/)
  assert.match(source, /看板数据加载失败，请稍后重试/)
})

test('最终 UI 门禁校验构建产物新于生产源码', () => {
  const source = read('deploy/tools/assert_ui_option2.mjs')

  assert.match(source, /latestSourceMtime/)
  assert.match(source, /distIndexMtime/)
  assert.match(source, /distIndexMtime\s*>=\s*latestSourceMtime/)
})
