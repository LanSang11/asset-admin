const VALID_SCOPES = new Set(['company', 'department', 'self'])

const EMPTY_TOTAL = Object.freeze({ assets: 0, employees: 0, in_use: 0, idle: 0 })
const EMPTY_PENDING = Object.freeze({ manager: 0, admin: 0, total: 0, my_applications: 0 })
const EMPTY_WARRANTY = Object.freeze({ expiring: 0, expired: 0, lead_days: 30, list: [] })

function count(value) {
  const number = Number(value)
  return Number.isFinite(number) && number > 0 ? number : 0
}

function list(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeDashboardScope(scope) {
  return VALID_SCOPES.has(scope) ? scope : 'self'
}

export function normalizeDashboardStats(input = {}) {
  const source = input && typeof input === 'object' ? input : {}
  const total = source.total && typeof source.total === 'object' ? source.total : EMPTY_TOTAL
  const pending =
    source.pending && typeof source.pending === 'object' ? source.pending : EMPTY_PENDING
  const warranty = source.warranty && typeof source.warranty === 'object' ? source.warranty : EMPTY_WARRANTY
  const trend = list(source.trend)
    .slice(-7)
    .map((item) => ({
      ...(item && typeof item === 'object' ? item : {}),
      date: String(item?.date ?? ''),
      领用: count(item?.领用),
      归还: count(item?.归还),
    }))

  return {
    ...source,
    scope: normalizeDashboardScope(source.scope),
    total: {
      assets: count(total.assets),
      employees: count(total.employees),
      in_use: count(total.in_use),
      idle: count(total.idle),
    },
    pending: {
      manager: count(pending.manager),
      admin: count(pending.admin),
      total: count(pending.total),
      my_applications: count(pending.my_applications),
    },
    category_stats: list(source.category_stats),
    status_stats: list(source.status_stats),
    dept_stats: list(source.dept_stats),
    trend,
    idle_list: list(source.idle_list),
    ranking: list(source.ranking),
    warranty: {
      expiring: count(warranty.expiring),
      expired: count(warranty.expired),
      lead_days: count(warranty.lead_days) || 30,
      list: list(warranty.list),
    },
  }
}

const SCOPE_COPY = Object.freeze({
  company: {
    subtitle: '全公司实时运营口径',
    idleTitle: '闲置资产（最近 10 台）',
    rankingTitle: '全公司员工资产排行',
  },
  department: {
    subtitle: '本部门归属数据 + 全公司可领用闲置池',
    idleTitle: '全公司可领用闲置（最近 10 台）',
    rankingTitle: '本部门员工资产排行',
  },
  self: {
    subtitle: '个人资产与申请摘要',
    idleTitle: '可领用闲置（摘要）',
    rankingTitle: '',
  },
})

export function getDashboardScopeCopy(scope) {
  return SCOPE_COPY[normalizeDashboardScope(scope)]
}

function warrantyMetric(stats, selfLabel) {
  const warranty = stats.warranty || EMPTY_WARRANTY
  const due = count(warranty.expiring) + count(warranty.expired)
  return {
    key: 'warranty',
    label: selfLabel,
    value: due,
    hint: warranty.expired ? `${warranty.expired} 台已过保` : `未来 ${warranty.lead_days || 30} 天`,
    tone: warranty.expired ? 'warning' : 'neutral',
  }
}

export function buildDashboardMetrics(input, scope = input?.scope) {
  const stats = normalizeDashboardStats({ ...(input || {}), scope })
  const { total, pending } = stats

  if (stats.scope === 'self') {
    return [
      {
        key: 'assets',
        label: '我的资产',
        value: total.assets,
        hint: '本人名下资产',
        tone: 'primary',
      },
      { key: 'in-use', label: '我的在用', value: total.in_use, hint: '当前在用', tone: 'success' },
      { key: 'idle', label: '可领用闲置', value: total.idle, hint: '脱敏摘要', tone: 'neutral' },
      {
        key: 'applications',
        label: '我的在途申请',
        value: pending.my_applications,
        hint: '处理中',
        tone: 'warning',
      },
      warrantyMetric(stats, '我的过保关注'),
    ]
  }

  const isDepartment = stats.scope === 'department'
  return [
    {
      key: 'assets',
      label: isDepartment ? '部门归属与可领用' : '资产总数',
      value: total.assets,
      hint: isDepartment ? '本部门归属 + 全司闲置' : '实时口径',
      tone: 'primary',
    },
    {
      key: 'employees',
      label: stats.scope === 'company' ? '在职员工' : '本部门员工',
      value: total.employees,
      hint: '当前范围',
      tone: 'neutral',
    },
    {
      key: 'in-use',
      label: isDepartment ? '部门在用资产' : '在用资产',
      value: total.in_use,
      hint: '当前在用',
      tone: 'success',
    },
    {
      key: 'idle',
      label: isDepartment ? '全司可领用闲置' : '闲置资产',
      value: total.idle,
      hint: isDepartment ? '公司闲置池' : '可调配',
      tone: 'info',
    },
    {
      key: 'pending',
      label: stats.scope === 'company' ? '待审批' : '本部门待审',
      value: pending.total,
      hint: '需处理',
      tone: 'warning',
    },
    warrantyMetric(stats, '过保关注'),
  ]
}

export function getTrendMax(trend = []) {
  const values = list(trend).flatMap((item) => [count(item?.领用), count(item?.归还)])
  return Math.max(1, ...values)
}

export function getTrendBarHeight(value, max) {
  const normalizedValue = count(value)
  if (!normalizedValue) return 0
  return Math.max(2, (normalizedValue / Math.max(1, count(max))) * 100)
}

const POSTURE_META = Object.freeze({
  login_failure: { label: '认证失败', tone: 'warning', hint: '保留登录失败明细' },
  scan: { label: '扫描', tone: 'danger', hint: '高频 404 按分钟聚合' },
  rate_limit: { label: '限流', tone: 'warning', hint: '触发频率限制' },
  blacklist_hit: { label: '黑名单命中', tone: 'danger', hint: '已被限制的请求' },
  permission_denied: { label: '权限拒绝', tone: 'neutral', hint: '无权限访问' },
})

function asFilter(value) {
  return value && typeof value === 'object' ? value : {}
}

export function normalizeSecurityPosture(input = {}) {
  const source = input && typeof input === 'object' ? input : {}
  const categories = list(source.categories).map((item) => {
    const key = String(item?.key || '')
    const meta = POSTURE_META[key] || { label: key || '事件', tone: 'neutral', hint: '' }
    return {
      key,
      label: item?.label || meta.label,
      count: count(item?.count),
      kind: String(item?.kind || ''),
      filter: asFilter(item?.filter),
      tone: meta.tone,
      hint: meta.hint,
    }
  })
  return {
    hours: count(source.hours) || 24,
    start_time: String(source.start_time || ''),
    end_time: String(source.end_time || ''),
    categories,
    hourly: list(source.hourly).map((item) => ({
      hour: String(item?.hour || ''),
      total: count(item?.total),
      login_failure: count(item?.login_failure),
      scan: count(item?.scan),
      rate_limit: count(item?.rate_limit),
      blacklist_hit: count(item?.blacklist_hit),
      permission_denied: count(item?.permission_denied),
      filter: asFilter(item?.filter),
    })),
    top_sources: list(source.top_sources).map((item) => ({
      ip: String(item?.ip || ''),
      count: count(item?.count),
      filter: asFilter(item?.filter),
    })),
    retention: source.retention && typeof source.retention === 'object' ? source.retention : {},
  }
}

export function buildSecurityPostureMetrics(posture) {
  return normalizeSecurityPosture(posture).categories.map((item) => ({
    key: item.key,
    label: item.label,
    value: item.count,
    hint: item.hint,
    tone: item.tone,
    filter: item.filter,
  }))
}

export function buildSecurityDrillQuery(filter = {}) {
  const query = {}
  const source = asFilter(filter)
  for (const key of [
    'tab',
    'event_type',
    'ip',
    'username',
    'start_time',
    'end_time',
    'success',
    'region',
    'exclude_region',
    'unknown_region',
  ]) {
    if (source[key] !== undefined && source[key] !== null && source[key] !== '') {
      query[key] = String(source[key])
    }
  }
  return query
}

export function getHourlyMax(hourly = []) {
  return Math.max(1, ...list(hourly).map((item) => count(item?.total)))
}
