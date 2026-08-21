import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDashboardMetrics,
  buildSecurityDrillQuery,
  getDashboardScopeCopy,
  getTrendBarHeight,
  getTrendMax,
  normalizeDashboardStats,
  normalizeSecurityPosture,
} from '../../../web/src/views/dashboard-model.js'

test('未知 scope 按 self 收紧且空数据被补为安全默认值', () => {
  const stats = normalizeDashboardStats({
    scope: 'unexpected',
    total: { assets: '12', employees: Number.POSITIVE_INFINITY },
    trend: null,
    ranking: null,
  })

  assert.equal(stats.scope, 'self')
  assert.equal(stats.total.assets, 12)
  assert.equal(stats.total.employees, 0)
  assert.deepEqual(stats.trend, [])
  assert.deepEqual(stats.ranking, [])
})

test('self 看板不生成公司员工数、全司待审批或排行文案', () => {
  const stats = normalizeDashboardStats({
    scope: 'self',
    total: { assets: 2, employees: 999, in_use: 1, idle: 4 },
    pending: { total: 999, my_applications: 3 },
  })
  const metrics = buildDashboardMetrics(stats, 'self')

  assert.equal(metrics.some((item) => item.label === '在职员工'), false)
  assert.equal(metrics.some((item) => item.label === '待审批'), false)
  assert.equal(metrics.some((item) => item.value === 999), false)
  assert.equal(metrics.find((item) => item.label === '我的在途申请')?.value, 3)
  assert.equal(metrics.find((item) => item.label === '我的过保关注')?.value, 0)
  assert.equal(getDashboardScopeCopy('self').rankingTitle, '')
})

test('过保关注从 warranty 计数且空数据补默认', () => {
  const stats = normalizeDashboardStats({
    scope: 'company',
    warranty: { expiring: '2', expired: 1, list: [{ asset_no: 'A1', name: '本' }] },
  })
  const metrics = buildDashboardMetrics(stats, 'company')

  assert.equal(stats.warranty.expiring, 2)
  assert.equal(stats.warranty.expired, 1)
  assert.equal(stats.warranty.list.length, 1)
  assert.equal(metrics.find((item) => item.key === 'warranty')?.value, 3)
  assert.equal(metrics.find((item) => item.key === 'warranty')?.label, '过保关注')
  assert.equal(normalizeDashboardStats({}).warranty.lead_days, 30)
})

test('department 文案区分本部门归属与全公司可领用闲置池', () => {
  const copy = getDashboardScopeCopy('department')
  const metrics = buildDashboardMetrics(
    {
      scope: 'department',
      total: { assets: 12, employees: 3, in_use: 4, idle: 8 },
      pending: { total: 2 },
    },
    'department'
  )

  assert.match(copy.subtitle, /本部门/)
  assert.match(copy.subtitle, /全公司可领用/)
  assert.match(copy.idleTitle, /全公司可领用/)
  assert.match(getDashboardScopeCopy('company').subtitle, /全公司/)
  assert.match(copy.rankingTitle, /本部门/)
  assert.match(metrics.find((item) => item.key === 'assets')?.hint || '', /本部门归属.*全司闲置/)
  assert.equal(metrics.find((item) => item.key === 'idle')?.label, '全司可领用闲置')
})

test('指标值只输出有限数字，趋势最大值最少为 1', () => {
  const stats = normalizeDashboardStats({
    scope: 'company',
    total: { assets: 'bad', employees: 8, in_use: -4, idle: 2 },
    pending: { total: Number.NaN },
  })
  const metrics = buildDashboardMetrics(stats, 'company')

  assert.equal(metrics.every((item) => Number.isFinite(item.value)), true)
  assert.equal(metrics.find((item) => item.label === '资产总数')?.value, 0)
  assert.equal(getTrendMax([]), 1)
  assert.equal(getTrendMax([{ date: 'd1', 领用: 0, 归还: 0 }]), 1)
  assert.equal(getTrendMax([{ date: 'd1', 领用: 4, 归还: 7 }]), 7)
  assert.equal(getTrendMax([{ date: 'd1', 领用: Number.POSITIVE_INFINITY, 归还: -2 }]), 1)
  assert.equal(getTrendBarHeight(0, 1), 0)
  assert.equal(getTrendBarHeight('bad', 10), 0)
  assert.equal(getTrendBarHeight(1, 100), 2)
  assert.equal(getTrendBarHeight(50, 100), 50)
})

test('安全态势数字有限且下钻 query 只带白名单字段', () => {
  const posture = normalizeSecurityPosture({
    categories: [{ key: 'login_failure', count: '9', filter: { tab: 'login', success: false } }],
    hourly: [{ hour: '2026-08-15 10:00:00', total: '3' }],
    top_sources: [{ ip: '1.2.3.4', count: 8, filter: { tab: 'attacks', ip: '1.2.3.4' } }],
  })
  assert.equal(posture.categories[0].count, 9)
  assert.equal(posture.hourly[0].total, 3)
  assert.deepEqual(buildSecurityDrillQuery({ tab: 'attacks', event_type: 'scan', extra: 'nope' }), {
    tab: 'attacks',
    event_type: 'scan',
  })
})

test('归一化不改变列表业务字段，仅截取最近七天趋势', () => {
  const input = Array.from({ length: 9 }, (_, index) => ({ date: `d${index}`, 领用: index, 归还: index + 1 }))
  const stats = normalizeDashboardStats({
    scope: 'company',
    trend: input,
    idle_list: [{ asset_no: 'A-1', name: '设备', location: 'L1' }],
  })

  assert.equal(stats.trend.length, 7)
  assert.equal(stats.trend[0].date, 'd2')
  assert.deepEqual(stats.idle_list[0], { asset_no: 'A-1', name: '设备', location: 'L1' })
})
