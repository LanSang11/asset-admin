<script setup>
import { h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NDrawer,
  NDrawerContent,
  NEmpty,
  NForm,
  NFormItem,
  NGrid,
  NGi,
  NInput,
  NInputNumber,
  NPopover,
  NSelect,
  NSpace,
  NStatistic,
  NSwitch,
  NTabPane,
  NTabs,
  NTag,
  useDialog,
} from 'naive-ui'
import CommonPage from '@/components/page/CommonPage.vue'
import api from '@/api'
import { withStepUp } from '@/composables'
import { useUserStore } from '@/store'

defineOptions({ name: '安全中心' })

const dialog = useDialog()
const route = useRoute()
const userStore = useUserStore()
const loading = ref(false)
const loginRows = ref([])
const loginTotal = ref(0)
const eventRows = ref([])
const eventTotal = ref(0)
const attackRows = ref([])
const attackTotal = ref(0)
const blacklistRows = ref([])
const retention = ref(null)
const loginPage = ref(1)
const eventPage = ref(1)
const attackPage = ref(1)
const pageSize = 20
const activeTab = ref('login')
const policyLoading = ref(false)
const verificationPolicy = ref({
  operations: [],
  login: { force_superuser: true, role_ids: [] },
  roles: [],
  root_operations: [],
  acceptance_mode: { active: false, expires_at: null, remaining_seconds: 0, duration_hours: 2 },
  password_rotate: { max_days: 0, deadline: null, enabled: false },
})
const passwordDeadlineTs = ref(null)
const acceptanceLoading = ref(false)
const tlsLoading = ref(false)
const tlsRenewing = ref(false)
const tlsStatus = ref({
  domain: 'asset.example.com',
  https_url: 'https://asset.example.com',
  http_fallback_url: 'http://127.0.0.1:9999',
  installed: false,
  issuer: '',
  not_before: null,
  not_after: null,
  days_left: null,
  last_cron_at: null,
  last_manual_renew_at: null,
  last_manual_result: '',
  suggested_window: '',
  auto_renew_mechanism: '',
})
const verificationModeOptions = [
  { label: '关闭', value: 'off' },
  { label: '登录密码', value: 'password' },
  { label: '动态验证码', value: 'totp' },
]

async function loadVerificationPolicies() {
  policyLoading.value = true
  try {
    const res = await api.getVerificationPolicies()
    applyVerificationPayload(res.data)
  } finally {
    policyLoading.value = false
  }
}

function applyVerificationPayload(data = {}) {
  const acceptance = data.acceptance_mode || {
    active: false,
    expires_at: null,
    remaining_seconds: 0,
    duration_hours: 2,
  }
  const rotate = data.password_rotate || { max_days: 0, deadline: null, enabled: false }
  verificationPolicy.value = {
    operations: (data.operations || []).map((item) => ({ ...item })),
    login: {
      force_superuser: data.login?.force_superuser !== false,
      role_ids: [...(data.login?.role_ids || [])],
    },
    roles: data.roles || [],
    root_operations: data.root_operations || [],
    acceptance_mode: acceptance,
    password_rotate: {
      max_days: Number(rotate.max_days || 0),
      deadline: rotate.deadline || null,
      enabled: !!rotate.enabled,
    },
  }
  passwordDeadlineTs.value = rotate.deadline ? Date.parse(rotate.deadline) : null
  userStore.setUserInfo({ acceptance_mode: acceptance })
}

async function saveVerificationPolicies() {
  policyLoading.value = true
  try {
    const payload = {
      operations: verificationPolicy.value.operations.map(({ operation_key, mode }) => ({
        operation_key,
        mode,
      })),
      login: {
        force_superuser: verificationPolicy.value.login.force_superuser,
        role_ids: verificationPolicy.value.login.role_ids,
      },
      password_rotate: {
        max_days: Number(verificationPolicy.value.password_rotate?.max_days || 0),
        deadline: passwordDeadlineTs.value
          ? new Date(passwordDeadlineTs.value).toISOString()
          : null,
      },
    }
    const res = await withStepUp('verification_policy_update', (headers) =>
      api.updateVerificationPolicies(payload, headers)
    )
    applyVerificationPayload(res.data)
    $message.success('二次验证策略已保存')
  } catch (e) {
    /* 取消或失败 */
  } finally {
    policyLoading.value = false
  }
}

function formatAcceptanceUntil(value) {
  const ts = Date.parse(value)
  if (!Number.isFinite(ts)) return ''
  const date = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getMonth() + 1}/${date.getDate()} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function enableAcceptanceMode() {
  acceptanceLoading.value = true
  try {
    const res = await withStepUp('acceptance_mode_update', (headers) =>
      api.updateAcceptanceMode({ enabled: true }, headers)
    )
    verificationPolicy.value.acceptance_mode = res.data
    userStore.setUserInfo({ acceptance_mode: res.data })
    $message.success(res.msg || '验收模式已开启')
  } catch (e) {
    /* 取消或失败 */
  } finally {
    acceptanceLoading.value = false
  }
}

function formatTlsTime(value) {
  if (!value) return '暂无'
  const ts = Date.parse(value)
  if (!Number.isFinite(ts)) return String(value)
  const date = new Date(ts)
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

async function loadTlsStatus() {
  tlsLoading.value = true
  try {
    const res = await api.getTlsStatus()
    tlsStatus.value = { ...tlsStatus.value, ...(res.data || {}) }
  } finally {
    tlsLoading.value = false
  }
}

async function renewTlsCert() {
  tlsRenewing.value = true
  try {
    const res = await withStepUp('tls_cert_renew', (headers) => api.renewTlsCert(headers))
    tlsStatus.value = { ...tlsStatus.value, ...(res.data || {}) }
    $message.success(res.msg || '续签已执行')
    await loadTlsStatus()
  } catch (e) {
    /* 取消或失败 */
  } finally {
    tlsRenewing.value = false
  }
}

async function disableAcceptanceMode() {
  acceptanceLoading.value = true
  try {
    const res = await api.updateAcceptanceMode({ enabled: false })
    verificationPolicy.value.acceptance_mode = res.data
    userStore.setUserInfo({ acceptance_mode: res.data })
    $message.success(res.msg || '验收模式已关闭')
  } catch (e) {
    /* 取消或失败 */
  } finally {
    acceptanceLoading.value = false
  }
}

const emptyQuery = () => ({
  username: '',
  ip: '',
  device_hash: '',
  success: null,
  region: '',
  exclude_region: '',
  unknown_region: null,
  range: null,
})
const loginQuery = ref({ ...emptyQuery() })
const eventQuery = ref({ event_type: null, ...emptyQuery() })
const attackQuery = ref({ event_type: null, ...emptyQuery() })
const successOptions = [
  { label: '全部结果', value: null },
  { label: '仅成功', value: true },
  { label: '仅失败', value: false },
]
const unknownRegionOptions = [
  { label: '地区不限', value: null },
  { label: '只要未知地区', value: true },
  { label: '排除未知地区', value: false },
]

const banForm = ref({ target: '', minutes: 15, reason: '' })
const dash = ref({
  login_success: 0,
  login_failure: 0,
  unique_ip: 0,
  ban_count: 0,
  auto_ban: false,
})
const tagHelpMap = ref({})
const deviceDrawer = ref(false)
const deviceUsername = ref('')
const deviceRows = ref([])

const EVENT_LABEL = {
  login_success: '登录成功',
  login_failure: '登录失败',
  ban: '封禁',
  unban: '解封',
  high_risk_delete: '高危删除',
  step_up: '二次验证',
  step_up_denied: '二次验证未过',
  reset_password: '重置密码',
  totp_bind: '绑定动态码',
  totp_disable: '关闭动态码',
  acceptance_mode: '验收模式',
  tls_renew: '证书续签',
  scan: '扫描',
  rate_limit: '限流',
  blacklist_hit: '黑名单命中',
  permission_denied: '权限拒绝',
  ai_policy: 'AI 策略',
}

const TAG_FALLBACK = {
  uncommon_country: { label: '非常见国家', level: 'warning', help: '登录来自不常见的国家/地区。可能是出差，也可能是代理。只提示，不会自动封。' },
  datacenter: { label: '机房 IP', level: 'warning', help: '运营商信息像云服务器或机房。不少代理走这里，也可能是正常云上办公。' },
  tor: { label: 'Tor 出口', level: 'error', help: '该 IP 出现在随发布带上的 Tor 出口快照里。应当高风险看待，不能单凭此定罪。' },
  tz_mismatch: { label: '时区对不上', level: 'warning', help: '浏览器时区和国家/地区明显对不上。可能是改了系统时区，也可能经过代理。' },
  new_device: { label: '新设备摘要', level: 'info', help: '这个账号以前没用过这个设备摘要。换浏览器、清站点数据都会变，高手也能假装。' },
  shared_device: { label: '多账号同摘要', level: 'warning', help: '同一个设备摘要出现在多个账号上。可能是共用电脑，也可能是被仿冒。' },
}

const eventTypeOptions = [
  { label: '全部', value: null },
  { label: '登录成功', value: 'login_success' },
  { label: '登录失败', value: 'login_failure' },
  { label: '封禁', value: 'ban' },
  { label: '解封', value: 'unban' },
  { label: '高危删除', value: 'high_risk_delete' },
  { label: '二次验证', value: 'step_up' },
  { label: '重置密码', value: 'reset_password' },
  { label: '动态码', value: 'totp_bind' },
]
const attackTypeOptions = [
  { label: '全部攻击', value: null },
  { label: '扫描', value: 'scan' },
  { label: '限流', value: 'rate_limit' },
  { label: '黑名单命中', value: 'blacklist_hit' },
  { label: '权限拒绝', value: 'permission_denied' },
]

function tagMeta(code) {
  return tagHelpMap.value[code] || TAG_FALLBACK[code] || { label: code, level: 'default', help: '风险提示，不是定罪。' }
}

function parseTags(row) {
  if (Array.isArray(row.risk_tag_list) && row.risk_tag_list.length) return row.risk_tag_list
  return String(row.risk_tags || '')
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean)
}

function toIso(ms) {
  if (!ms) return undefined
  return new Date(ms).toISOString()
}

function queryParams(source, extra = {}) {
  return {
    username: source.username || undefined,
    ip: source.ip || undefined,
    device_hash: source.device_hash || undefined,
    region: source.region || undefined,
    exclude_region: source.exclude_region || undefined,
    success: source.success === true || source.success === false ? source.success : undefined,
    unknown_region:
      source.unknown_region === true || source.unknown_region === false ? source.unknown_region : undefined,
    start_time: Array.isArray(source.range) ? toIso(source.range[0]) : undefined,
    end_time: Array.isArray(source.range) ? toIso(source.range[1]) : undefined,
    ...extra,
  }
}

function activeChips(source) {
  const chips = []
  if (source.success === true) chips.push({ key: 'success', label: '结果：成功' })
  if (source.success === false) chips.push({ key: 'success', label: '结果：失败' })
  if (source.username) chips.push({ key: 'username', label: `用户：${source.username}` })
  if (source.ip) chips.push({ key: 'ip', label: `IP：${source.ip}` })
  if (source.device_hash) chips.push({ key: 'device_hash', label: `设备：${source.device_hash}` })
  if (source.region) chips.push({ key: 'region', label: `地区是：${source.region}` })
  if (source.exclude_region) chips.push({ key: 'exclude_region', label: `地区不是：${source.exclude_region}` })
  if (source.unknown_region === true) chips.push({ key: 'unknown_region', label: '只要未知地区' })
  if (source.unknown_region === false) chips.push({ key: 'unknown_region', label: '排除未知地区' })
  if (Array.isArray(source.range) && source.range.length === 2) chips.push({ key: 'range', label: '已指定时间段' })
  if (source.event_type) chips.push({ key: 'event_type', label: EVENT_LABEL[source.event_type] || source.event_type })
  return chips
}

function removeChip(target, key, reload) {
  if (key === 'success' || key === 'unknown_region' || key === 'event_type') target[key] = null
  else if (key === 'range') target.range = null
  else target[key] = ''
  reload()
}

function resetLoginFilter() {
  loginQuery.value = { ...emptyQuery() }
  loginPage.value = 1
  loadLogin()
}

function resetEventFilter() {
  eventQuery.value = { event_type: null, ...emptyQuery() }
  eventPage.value = 1
  loadEvents()
}

function resetAttackFilter() {
  attackQuery.value = { event_type: null, ...emptyQuery() }
  attackPage.value = 1
  loadAttacks()
}

function parseQueryBool(value) {
  if (value === true || value === 'true') return true
  if (value === false || value === 'false') return false
  return null
}

function applyRouteFilter() {
  const q = route.query || {}
  const tab = String(q.tab || '')
  if (['login', 'events', 'attacks', 'ban', 'verification'].includes(tab)) activeTab.value = tab
  const range =
    q.start_time && q.end_time ? [new Date(q.start_time).getTime(), new Date(q.end_time).getTime()] : null
  const common = {
    ...emptyQuery(),
    username: q.username ? String(q.username) : '',
    ip: q.ip ? String(q.ip) : '',
    device_hash: q.device_hash ? String(q.device_hash) : '',
    region: q.region ? String(q.region) : '',
    exclude_region: q.exclude_region ? String(q.exclude_region) : '',
    success: q.success === undefined ? null : parseQueryBool(q.success),
    unknown_region: q.unknown_region === undefined ? null : parseQueryBool(q.unknown_region),
    range,
  }
  const eventType = q.event_type ? String(q.event_type) : null
  if (tab === 'login' || eventType === 'login_failure') {
    loginQuery.value = { ...common, success: common.success === null ? false : common.success }
  }
  eventQuery.value = { event_type: eventType, ...common }
  attackQuery.value = { event_type: eventType, ...common }
}

function filterByIp(ip) {
  if (!ip) return
  loginQuery.value.ip = ip
  eventQuery.value.ip = ip
  loginPage.value = 1
  eventPage.value = 1
  activeTab.value = 'login'
  loadLogin()
}

function filterByDevice(hash) {
  if (!hash) return
  loginQuery.value.device_hash = hash
  eventQuery.value.device_hash = hash
  loginPage.value = 1
  eventPage.value = 1
  activeTab.value = 'login'
  loadLogin()
}

function filterByUser(username) {
  if (!username) return
  loginQuery.value.username = username
  loginPage.value = 1
  activeTab.value = 'login'
  loadLogin()
  openUserDevices(username)
}

async function openUserDevices(username) {
  deviceUsername.value = username
  deviceDrawer.value = true
  try {
    const res = await api.getSecurityUserDevices({ username })
    deviceRows.value = res.data || []
  } catch (e) {
    deviceRows.value = []
  }
}

function renderTags(row) {
  const tags = parseTags(row)
  if (!tags.length) return h('span', { style: 'color:#999' }, '无')
  return h(
    NSpace,
    { size: 4, wrap: true },
    {
      default: () =>
        tags.map((code) => {
          const meta = tagMeta(code)
          return h(
            NPopover,
            { trigger: 'click' },
            {
              trigger: () =>
                h(NTag, { type: meta.level || 'default', size: 'small', style: 'cursor:pointer' }, () => meta.label),
              default: () => meta.help,
            }
          )
        }),
    }
  )
}

function makeColumns() {
  return [
    { title: '时间', key: 'created_at', width: 168 },
    {
      title: '类型',
      key: 'event_type',
      width: 110,
      render: (row) => EVENT_LABEL[row.event_type] || row.event_type,
    },
    {
      title: '用户',
      key: 'username',
      width: 110,
      render: (row) =>
        row.username
          ? h(
              NButton,
              { text: true, type: 'primary', onClick: () => filterByUser(row.username) },
              () => row.username
            )
          : h('span', { style: 'color:#999' }, '—'),
    },
    {
      title: 'IP',
      key: 'ip',
      width: 132,
      render: (row) =>
        h(NButton, { text: true, type: 'primary', onClick: () => filterByIp(row.ip) }, () => row.ip || '—'),
    },
    {
      title: '国家/地区',
      key: 'location',
      width: 140,
      ellipsis: { tooltip: true },
      render: (row) => row.location || (row.country ? `${row.country}${row.region ? ' / ' + row.region : ''}` : '未知'),
    },
    { title: '运营商', key: 'isp', width: 110, ellipsis: { tooltip: true } },
    {
      title: '风险提示',
      key: 'risk_tags',
      width: 220,
      render: (row) => renderTags(row),
    },
    {
      title: '设备摘要',
      key: 'device_hash',
      width: 132,
      render: (row) =>
        row.device_hash
          ? h(
              NButton,
              { text: true, type: 'primary', onClick: () => filterByDevice(row.device_hash) },
              () => row.device_hash
            )
          : '—',
    },
    {
      title: '结果',
      key: 'success',
      width: 72,
      render: (row) =>
        h(NTag, { type: row.success ? 'success' : 'error', size: 'small' }, () => (row.success ? '成功' : '失败')),
    },
    { title: '详情', key: 'detail', ellipsis: { tooltip: true }, minWidth: 140 },
  ]
}

const loginColumns = makeColumns()
const eventColumns = makeColumns()
const attackColumns = [
  { title: '分钟桶', key: 'bucket_minute', width: 168 },
  {
    title: '类型',
    key: 'event_type',
    width: 120,
    render: (row) => EVENT_LABEL[row.event_type] || row.event_type,
  },
  { title: '次数', key: 'hit_count', width: 80 },
  { title: '来源', key: 'source_key', width: 160 },
  { title: 'IP', key: 'ip', width: 140 },
  {
    title: '国家/地区',
    key: 'location',
    ellipsis: { tooltip: true },
    render: (row) => row.location || (row.country ? `${row.country}${row.region ? ' / ' + row.region : ''}` : '未知'),
  },
  { title: '首次', key: 'first_seen', width: 168 },
  { title: '末次', key: 'last_seen', width: 168 },
]

const blacklistColumns = [
  { title: '对象', key: 'key', width: 200 },
  { title: '来源', key: 'source', width: 90 },
  { title: '原因', key: 'reason', ellipsis: { tooltip: true } },
  {
    title: '剩余',
    key: 'remain_seconds',
    width: 100,
    render: (row) => {
      const s = row.remain_seconds || 0
      if (s > 86400 * 30) return '长期'
      if (s >= 3600) return `${Math.ceil(s / 3600)} 小时`
      return `${Math.ceil(s / 60)} 分钟`
    },
  },
  {
    title: '操作',
    key: 'actions',
    width: 100,
    render: (row) =>
      h(
        NButton,
        {
          size: 'small',
          type: 'warning',
          onClick: () => handleUnban(row.key),
        },
        () => '解封'
      ),
  },
]

const deviceColumns = [
  { title: '设备摘要', key: 'device_hash', width: 140 },
  { title: '最近一次', key: 'last_seen', width: 168 },
  { title: '最早一次', key: 'first_seen', width: 168 },
  { title: '次数', key: 'login_count', width: 70 },
  { title: '最近 IP', key: 'ip', width: 130 },
  { title: '国家/地区', key: 'location', ellipsis: { tooltip: true } },
  { title: '风险提示', key: 'risk_tags', render: (row) => renderTags(row) },
]

async function loadDashboard() {
  try {
    const res = await api.getSecurityDashboard()
    dash.value = res.data || dash.value
  } catch (e) {
    /* 超管锁失败时保持 0 */
  }
}

async function loadTagHelp() {
  try {
    const res = await api.getSecurityTagHelp()
    const map = {}
    for (const item of res.data || []) {
      if (item.code) map[item.code] = item
    }
    tagHelpMap.value = map
  } catch (e) {
    tagHelpMap.value = {}
  }
}

async function loadLogin() {
  loading.value = true
  try {
    const res = await api.getLoginEvents({
      page: loginPage.value,
      page_size: pageSize,
      ...queryParams(loginQuery.value),
    })
    loginRows.value = res.data || []
    loginTotal.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadEvents() {
  loading.value = true
  try {
    const res = await api.getSecurityEvents({
      page: eventPage.value,
      page_size: pageSize,
      ...queryParams(eventQuery.value, { event_type: eventQuery.value.event_type || undefined }),
    })
    eventRows.value = res.data || []
    eventTotal.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadAttacks() {
  loading.value = true
  try {
    const res = await api.getAttackAgg({
      page: attackPage.value,
      page_size: pageSize,
      ...queryParams(attackQuery.value, { event_type: attackQuery.value.event_type || undefined }),
    })
    attackRows.value = res.data || []
    attackTotal.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadBlacklist() {
  const res = await api.getBlacklist()
  const data = res.data || {}
  blacklistRows.value = Object.keys(data).map((key) => ({
    key,
    ...(data[key] || {}),
  }))
}

async function loadRetention() {
  try {
    const res = await api.getSecurityRetention()
    retention.value = res.data
  } catch (e) {
    retention.value = null
  }
}

async function handleBan() {
  if (!banForm.value.target) {
    $message.warning('请输入 IP 或 uid')
    return
  }
  try {
    await withStepUp('blacklist_ban', (headers) =>
      api.banBlacklist(
        {
          target: banForm.value.target,
          minutes: banForm.value.minutes,
          reason: banForm.value.reason || '管理员手动封禁',
        },
        headers
      )
    )
    $message.success('已封禁')
    banForm.value = { target: '', minutes: 15, reason: '' }
    await loadBlacklist()
    await loadEvents()
    await loadDashboard()
  } catch (e) {
    /* 取消或失败 */
  }
}

async function handleUnban(key) {
  dialog.warning({
    title: '确认解封',
    content: `解封 ${key}？需验证登录密码。`,
    positiveText: '解封',
    negativeText: '取消',
    onPositiveClick: async () => {
      try {
        await withStepUp('blacklist_unban', (headers) => api.unbanBlacklist({ key }, headers))
        $message.success('已解封')
        await loadBlacklist()
        await loadEvents()
        await loadDashboard()
      } catch (e) {
        /* ignore */
      }
    },
  })
}

onMounted(() => {
  applyRouteFilter()
  loadDashboard()
  loadTagHelp()
  loadLogin()
  loadEvents()
  loadAttacks()
  loadBlacklist()
  loadRetention()
  loadVerificationPolicies()
  loadTlsStatus()
})
</script>

<template>
  <CommonPage title="安全中心">
    <NAlert type="info" :bordered="false" class="mb-12" title="怎么看这些数字（给管理员）">
      <div class="help-lines">
        <p>登录日志只记录「谁、何时、从哪个 IP 进来、成功还是失败」，<strong>不是抓人证明</strong>。</p>
        <p>国家/地区来自离线库，公司宽带一般准；代理会骗人。机房 / Tor / 时区对不上只是<strong>风险提示</strong>，系统不会自动封。</p>
        <p>可以按「成功/失败、时间段、地区是/不是」组合筛选。排除「上海」时，未知地区会单独留下来，不会被算进上海之外。</p>
        <p>设备摘要是浏览器的「长相编号」，换电脑或清站点数据常会变，高手能假装。点 IP 或摘要可只看这一条线。</p>
        <p>封一个 IP 会挡住所有从该出口上网的人（公司、网吧、家庭宽带会误伤一串）。封禁前请再输密码确认。</p>
      </div>
    </NAlert>

    <NGrid cols="1 600:2 900:4" :x-gap="12" :y-gap="12" class="mb-12">
      <NGi>
        <NCard size="small">
          <NStatistic label="近 24 小时登录成功" :value="dash.login_success" />
        </NCard>
      </NGi>
      <NGi>
        <NCard size="small">
          <NStatistic label="近 24 小时登录失败" :value="dash.login_failure" />
        </NCard>
      </NGi>
      <NGi>
        <NCard size="small">
          <NStatistic label="近 24 小时独立 IP" :value="dash.unique_ip" />
        </NCard>
      </NGi>
      <NGi>
        <NCard size="small">
          <NStatistic label="当前封禁数" :value="dash.ban_count" />
        </NCard>
      </NGi>
    </NGrid>

    <NCard v-if="retention" size="small" class="mb-12" title="日志保留（防止日志把磁盘写满）">
      <div class="text-14" style="color: #666; line-height: 1.8">
        操作审计：{{ retention.audit_retention_days }} 天或最多
        {{ retention.audit_max_rows }} 行；安全事件明细：{{ retention.security_event_retention_days }}
        天或最多 {{ retention.security_event_max_rows }} 行；攻击聚合：{{
          retention.security_agg_retention_days || 180
        }}
        天或最多 {{ retention.security_agg_max_rows || 200000 }} 行。本页<strong>不会自动封禁</strong>任何人。
      </div>
    </NCard>

    <NTabs v-model:value="activeTab" type="line" animated>
      <NTabPane name="login" tab="登录日志">
        <NSpace class="mb-12" wrap>
          <NSelect v-model:value="loginQuery.success" :options="successOptions" style="width: 120px" />
          <NDatePicker v-model:value="loginQuery.range" type="datetimerange" clearable style="width: 360px" />
          <NInput v-model:value="loginQuery.username" placeholder="用户名" clearable style="width: 140px" />
          <NInput v-model:value="loginQuery.ip" placeholder="点表格 IP 可过滤" clearable style="width: 160px" />
          <NInput
            v-model:value="loginQuery.device_hash"
            placeholder="点设备摘要可过滤"
            clearable
            style="width: 180px"
          />
          <NInput v-model:value="loginQuery.region" placeholder="地区是" clearable style="width: 110px" />
          <NInput v-model:value="loginQuery.exclude_region" placeholder="地区不是" clearable style="width: 110px" />
          <NSelect v-model:value="loginQuery.unknown_region" :options="unknownRegionOptions" style="width: 150px" />
          <NButton type="primary" @click=";(loginPage = 1), loadLogin()">查询</NButton>
          <NButton @click="resetLoginFilter">清空过滤</NButton>
        </NSpace>
        <NSpace v-if="activeChips(loginQuery).length" class="mb-12" wrap>
          <NTag
            v-for="chip in activeChips(loginQuery)"
            :key="chip.key + chip.label"
            closable
            @close="removeChip(loginQuery, chip.key, () => { loginPage = 1; loadLogin() })"
          >
            {{ chip.label }}
          </NTag>
        </NSpace>
        <NDataTable
          :columns="loginColumns"
          :data="loginRows"
          :loading="loading"
          :bordered="false"
          size="small"
          :scroll-x="1400"
        />
        <NEmpty v-if="!loading && !loginRows.length" description="这段时间没有登录记录" class="mt-12" />
        <NSpace justify="end" class="mt-12">
          <NButton :disabled="loginPage <= 1" @click=";(loginPage -= 1), loadLogin()">上一页</NButton>
          <span>第 {{ loginPage }} 页 / 共 {{ loginTotal }} 条</span>
          <NButton :disabled="loginPage * pageSize >= loginTotal" @click=";(loginPage += 1), loadLogin()">下一页</NButton>
        </NSpace>
      </NTabPane>

      <NTabPane name="events" tab="安全事件">
        <NSpace class="mb-12" wrap>
          <NSelect v-model:value="eventQuery.event_type" :options="eventTypeOptions" style="width: 160px" clearable />
          <NSelect v-model:value="eventQuery.success" :options="successOptions" style="width: 120px" />
          <NDatePicker v-model:value="eventQuery.range" type="datetimerange" clearable style="width: 360px" />
          <NInput v-model:value="eventQuery.username" placeholder="用户名" clearable style="width: 140px" />
          <NInput v-model:value="eventQuery.ip" placeholder="IP" clearable style="width: 140px" />
          <NInput v-model:value="eventQuery.device_hash" placeholder="设备摘要" clearable style="width: 160px" />
          <NInput v-model:value="eventQuery.region" placeholder="地区是" clearable style="width: 110px" />
          <NInput v-model:value="eventQuery.exclude_region" placeholder="地区不是" clearable style="width: 110px" />
          <NSelect v-model:value="eventQuery.unknown_region" :options="unknownRegionOptions" style="width: 150px" />
          <NButton type="primary" @click=";(eventPage = 1), loadEvents()">查询</NButton>
          <NButton @click="resetEventFilter">清空过滤</NButton>
        </NSpace>
        <NSpace v-if="activeChips(eventQuery).length" class="mb-12" wrap>
          <NTag
            v-for="chip in activeChips(eventQuery)"
            :key="chip.key + chip.label"
            closable
            @close="removeChip(eventQuery, chip.key, () => { eventPage = 1; loadEvents() })"
          >
            {{ chip.label }}
          </NTag>
        </NSpace>
        <NDataTable
          :columns="eventColumns"
          :data="eventRows"
          :loading="loading"
          :bordered="false"
          size="small"
          :scroll-x="1400"
        />
        <NEmpty v-if="!loading && !eventRows.length" description="没有匹配的安全事件" class="mt-12" />
        <NSpace justify="end" class="mt-12">
          <NButton :disabled="eventPage <= 1" @click=";(eventPage -= 1), loadEvents()">上一页</NButton>
          <span>第 {{ eventPage }} 页 / 共 {{ eventTotal }} 条</span>
          <NButton :disabled="eventPage * pageSize >= eventTotal" @click=";(eventPage += 1), loadEvents()">下一页</NButton>
        </NSpace>
      </NTabPane>

      <NTabPane name="attacks" tab="攻击聚合">
        <NAlert type="info" :bordered="false" class="mb-12">
          扫描、限流、黑名单命中、权限拒绝按分钟汇总，不逐条写一万行。登录失败仍在「登录日志」。
        </NAlert>
        <NSpace class="mb-12" wrap>
          <NSelect v-model:value="attackQuery.event_type" :options="attackTypeOptions" style="width: 160px" clearable />
          <NDatePicker v-model:value="attackQuery.range" type="datetimerange" clearable style="width: 360px" />
          <NInput v-model:value="attackQuery.ip" placeholder="IP" clearable style="width: 140px" />
          <NInput v-model:value="attackQuery.region" placeholder="地区是" clearable style="width: 110px" />
          <NInput v-model:value="attackQuery.exclude_region" placeholder="地区不是" clearable style="width: 110px" />
          <NSelect v-model:value="attackQuery.unknown_region" :options="unknownRegionOptions" style="width: 150px" />
          <NButton type="primary" @click=";(attackPage = 1), loadAttacks()">查询</NButton>
          <NButton @click="resetAttackFilter">清空过滤</NButton>
        </NSpace>
        <NSpace v-if="activeChips(attackQuery).length" class="mb-12" wrap>
          <NTag
            v-for="chip in activeChips(attackQuery)"
            :key="chip.key + chip.label"
            closable
            @close="removeChip(attackQuery, chip.key, () => { attackPage = 1; loadAttacks() })"
          >
            {{ chip.label }}
          </NTag>
        </NSpace>
        <NDataTable
          :columns="attackColumns"
          :data="attackRows"
          :loading="loading"
          :bordered="false"
          size="small"
          :scroll-x="1200"
        />
        <NEmpty v-if="!loading && !attackRows.length" description="没有匹配的攻击聚合" class="mt-12" />
        <NSpace justify="end" class="mt-12">
          <NButton :disabled="attackPage <= 1" @click=";(attackPage -= 1), loadAttacks()">上一页</NButton>
          <span>第 {{ attackPage }} 页 / 共 {{ attackTotal }} 条</span>
          <NButton :disabled="attackPage * pageSize >= attackTotal" @click=";(attackPage += 1), loadAttacks()">下一页</NButton>
        </NSpace>
      </NTabPane>

      <NTabPane name="ban" tab="IP / 账号封禁">
        <NAlert type="warning" :bordered="false" class="mb-12">
          封 IP 会挡住所有走这个出口的人。风险提示（机房、非常见国家等）<strong>不会自动封</strong>，需要你自己判断再动手。
        </NAlert>
        <NCard size="small" title="手动封禁" class="mb-12">
          <NForm label-placement="left" label-width="80">
            <NFormItem label="目标">
              <NInput
                v-model:value="banForm.target"
                placeholder="IP 如 1.2.3.4，或 uid:1 / 用户数字 ID"
                style="max-width: 360px"
              />
            </NFormItem>
            <NFormItem label="时长(分)">
              <NInputNumber v-model:value="banForm.minutes" :min="0" style="width: 160px" />
              <span class="ml-8" style="color: #888">0 = 长期封禁</span>
            </NFormItem>
            <NFormItem label="原因">
              <NInput v-model:value="banForm.reason" placeholder="备注（写入安全事件）" style="max-width: 360px" />
            </NFormItem>
            <NFormItem>
              <NButton type="error" @click="handleBan">按当前策略验证并封禁</NButton>
              <NButton class="ml-8" @click="loadBlacklist">刷新列表</NButton>
            </NFormItem>
          </NForm>
        </NCard>
        <NDataTable :columns="blacklistColumns" :data="blacklistRows" :bordered="false" size="small" />
        <NEmpty v-if="!blacklistRows.length" description="当前没有封禁" class="mt-12" />
      </NTabPane>

      <NTabPane name="verification" tab="二次验证策略">
        <NAlert type="warning" :bordered="false" class="mb-12">
          每个高危动作独立设置，互不联动。修改本页本身固定要求当前超级管理员输入动态验证码，不能关闭。
        </NAlert>
        <NCard size="small" title="限时验收模式" class="mb-12">
          <NAlert type="error" :bordered="false" class="mb-12">
            只给开发/验收临时用。开启后 2 小时内，已绑定账号登录不再要动态码；到期自动恢复。导出、删资产、改策略等逐项验证和根保护都不会关。开启必须输入当前验证器动态码。
          </NAlert>
          <p class="mb-12">
            当前状态：
            <strong>{{ verificationPolicy.acceptance_mode?.active ? '开启中' : '已关闭' }}</strong>
            <span v-if="verificationPolicy.acceptance_mode?.active && verificationPolicy.acceptance_mode?.expires_at">
              ，到期 {{ formatAcceptanceUntil(verificationPolicy.acceptance_mode.expires_at) }}
            </span>
          </p>
          <NSpace>
            <NButton type="warning" :loading="acceptanceLoading" @click="enableAcceptanceMode">
              验证动态码并开启 / 续期 2 小时
            </NButton>
            <NButton
              v-if="verificationPolicy.acceptance_mode?.active"
              :loading="acceptanceLoading"
              @click="disableAcceptanceMode"
            >
              提前关闭
            </NButton>
          </NSpace>
        </NCard>
        <NCard size="small" title="到期换密（默认关闭）" class="mb-12">
          <NAlert type="info" :bordered="false" class="mb-12">
            关掉时不影响任何人。打开后，超过最长天数或到截止日期的账号登录后只能改密（沿用已有强制改密流程）。
          </NAlert>
          <NForm label-placement="left" label-width="180">
            <NFormItem label="密码最长天数">
              <NInputNumber
                v-model:value="verificationPolicy.password_rotate.max_days"
                :min="0"
                :max="3650"
                placeholder="0 表示不按天数过期"
                style="max-width: 220px"
              />
            </NFormItem>
            <NFormItem label="全员截止日期">
              <NDatePicker v-model:value="passwordDeadlineTs" type="date" clearable />
            </NFormItem>
          </NForm>
        </NCard>
        <NCard size="small" title="登录强制验证" class="mb-12">
          <NForm label-placement="left" label-width="180">
            <NFormItem label="超级管理员登录强制 TOTP">
              <NSwitch v-model:value="verificationPolicy.login.force_superuser" />
            </NFormItem>
            <NFormItem label="额外强制角色">
              <NSelect
                v-model:value="verificationPolicy.login.role_ids"
                multiple
                clearable
                :options="verificationPolicy.roles.map((role) => ({ label: role.name, value: role.id }))"
                placeholder="未选择时只按超级管理员开关执行"
                style="max-width: 520px"
              />
            </NFormItem>
          </NForm>
        </NCard>
        <NCard size="small" title="逐项高危操作" class="mb-12">
          <NGrid cols="1 760:2" :x-gap="16" :y-gap="8">
            <NGi v-for="item in verificationPolicy.operations" :key="item.operation_key">
              <div class="verification-row">
                <div>
                  <strong>{{ item.label }}</strong>
                  <div class="verification-key">{{ item.operation_key }}</div>
                </div>
                <NSelect v-model:value="item.mode" :options="verificationModeOptions" style="width: 140px" />
              </div>
            </NGi>
          </NGrid>
        </NCard>
        <NCard size="small" title="根保护（固定不可关闭）" class="mb-12">
          <NSpace vertical>
            <div v-for="item in verificationPolicy.root_operations" :key="item.operation_key" class="verification-row">
              <div>
                <strong>{{ item.label }}</strong>
                <div class="verification-key">{{ item.operation_key }}</div>
              </div>
              <NTag type="error">动态验证码</NTag>
            </div>
          </NSpace>
        </NCard>
        <NButton type="primary" :loading="policyLoading" @click="saveVerificationPolicies">
          验证动态码并保存
        </NButton>
        <NButton class="ml-8" :loading="policyLoading" @click="loadVerificationPolicies">恢复线上设置</NButton>
      </NTabPane>

      <NTabPane name="tls" tab="HTTPS 证书">
        <NAlert type="info" :bordered="false" class="mb-12">
          免费证书由宝塔每天自动检查续签。这里可以查看到期时间，也可以点「立即续签」。续签要输入当前验证器动态码。未到窗口时会提示跳过，不会关掉旧证书。
        </NAlert>
        <NCard size="small" title="当前证书" :loading="tlsLoading">
          <p class="mb-12">
            访问地址：
            <a :href="tlsStatus.https_url" target="_blank" rel="noopener">{{ tlsStatus.https_url }}</a>
          </p>
          <p class="mb-12">旧入口仍可用：{{ tlsStatus.http_fallback_url }}</p>
          <p class="mb-12">域名：<strong>{{ tlsStatus.domain || 'asset.example.com' }}</strong></p>
          <p class="mb-12">签发机构：{{ tlsStatus.issuer || '尚未读取到证书' }}</p>
          <p class="mb-12">签发时间：{{ formatTlsTime(tlsStatus.not_before) }}</p>
          <p class="mb-12">到期时间：<strong>{{ formatTlsTime(tlsStatus.not_after) }}</strong></p>
          <p class="mb-12">
            剩余天数：
            <strong>{{ tlsStatus.days_left == null ? '未知' : tlsStatus.days_left + ' 天' }}</strong>
          </p>
          <p class="mb-12">自动续签：{{ tlsStatus.auto_renew_mechanism || '宝塔每日定时' }}</p>
          <p class="mb-12">最近自动检查：{{ tlsStatus.last_cron_at || '暂无' }}</p>
          <p class="mb-12">建议窗口：{{ tlsStatus.suggested_window || '以证书到期前约 30 天为准' }}</p>
          <p class="mb-12">最近手动续签：{{ formatTlsTime(tlsStatus.last_manual_renew_at) }}</p>
          <p class="mb-12">最近手动结果：{{ tlsStatus.last_manual_result || '尚未手动续签' }}</p>
          <NSpace>
            <NButton type="primary" :loading="tlsRenewing" @click="renewTlsCert">立即续签</NButton>
            <NButton :loading="tlsLoading" @click="loadTlsStatus">刷新状态</NButton>
          </NSpace>
        </NCard>
      </NTabPane>
    </NTabs>

    <NDrawer v-model:show="deviceDrawer" :width="720">
      <NDrawerContent :title="`账号 ${deviceUsername} 的近次设备摘要`">
        <p style="color: #666; margin-bottom: 12px">
          只给超管看编号，不是硬件身份证。换浏览器或清数据会出现「新设备摘要」。
        </p>
        <NDataTable :columns="deviceColumns" :data="deviceRows" :bordered="false" size="small" />
        <NEmpty v-if="!deviceRows.length" description="这个账号还没有设备摘要记录" class="mt-12" />
      </NDrawerContent>
    </NDrawer>
  </CommonPage>
</template>

<style scoped>
.mb-12 {
  margin-bottom: 12px;
}
.mt-12 {
  margin-top: 12px;
}
.ml-8 {
  margin-left: 8px;
}
.help-lines p {
  margin: 0 0 4px;
  line-height: 1.7;
}
.help-lines p:last-child {
  margin-bottom: 0;
}
.verification-row {
  min-height: 54px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 8px 12px;
  border: 1px solid rgba(128, 128, 128, 0.18);
  border-radius: 8px;
}
.verification-key {
  margin-top: 3px;
  color: #888;
  font-size: 12px;
}
</style>
