const ROUTE_FIELD_LABELS = [
  [/\/base\/update_password/i, { old_password: '旧密码', new_password: '新密码' }],
  [/\/user\//i, { username: '用户名称', email: '邮箱', password: '密码', role_ids: '角色' }],
  [
    /\/asset\//i,
    {
      asset_no: '资产编号',
      name: '资产名称',
      category: '资产分类',
      model: '型号',
      serial_no: '序列号',
      purchase_date: '采购日期',
      warranty_until: '质保到期日',
      price: '采购价格',
      location: '存放位置',
      remark: '备注',
    },
  ],
  [
    /\/employee\//i,
    {
      emp_no: '工号',
      name: '姓名',
      position: '职位',
      hire_date: '入职日期',
      phone: '手机',
      email: '邮箱',
    },
  ],
  [/\/asset-repair\//i, { asset_id: '资产', reason: '故障说明', comment: '处理说明' }],
  [/\/asset-transfer\//i, { asset_id: '资产', to_employee_id: '调入人员', reason: '调拨说明' }],
  [/\/inventory\//i, { title: '盘点名称', note: '备注' }],
  [/\/dept\//i, { name: '部门名称', desc: '备注', parent_id: '上级部门' }],
  [/\/role\//i, { name: '角色名称', desc: '角色描述' }],
  [
    /\/menu\//i,
    { name: '菜单名称', path: '菜单路径', icon: '菜单图标', component: '组件', redirect: '重定向' },
  ],
  [/\/v1\/api\//i, { path: 'API 路径', summary: 'API 简介', method: '请求方法', tags: 'API 标签' }],
]

const COMMON_FIELD_LABELS = {
  page: '页码',
  page_size: '每页数量',
  id: '记录',
  email: '邮箱',
  username: '用户名称',
  password: '密码',
  new_password: '新密码',
  old_password: '旧密码',
  name: '名称',
  title: '名称',
  reason: '说明',
}

function fieldLabel(field, requestUrl) {
  const routeLabels = ROUTE_FIELD_LABELS.find(([pattern]) => pattern.test(requestUrl || ''))?.[1]
  return routeLabels?.[field] || COMMON_FIELD_LABELS[field] || '相关字段'
}

function safeDetailMessage(detail) {
  const type = detail?.type || ''
  const message = typeof detail?.msg === 'string' ? detail.msg : ''
  if (/^[\u3400-\u9fff]/.test(message)) return message

  const matchers = [
    ['missing', '不能为空'],
    ['int_parsing', '请输入整数'],
    ['float_parsing', '请输入有效数字'],
    ['decimal_parsing', '请输入有效数字'],
    ['bool_parsing', '请选择有效状态'],
    ['date_parsing', '请输入有效日期'],
    ['literal_error', '请选择有效选项'],
    ['enum', '请选择有效选项'],
  ]
  const matched = matchers.find(([errorType]) => type === errorType)
  if (matched) return matched[1]

  const number = message.match(/(?:at least|at most|equal to)\s+(\d+)/i)?.[1]
  if (type === 'string_too_short' && number) return `至少输入 ${number} 个字符`
  if (type === 'string_too_long' && number) return `最多输入 ${number} 个字符`
  if (type === 'greater_than_equal' && number) return `需大于或等于 ${number}`
  if (type === 'less_than_equal' && number) return `需小于或等于 ${number}`
  return '填写内容不符合要求'
}

export function formatValidationMessage(payload, requestUrl = '') {
  const details = Array.isArray(payload?.data) ? payload.data : []
  if (!details.length) return payload?.msg || '请求未完成，请检查填写内容后重试'

  const messages = []
  const seen = new Set()
  for (const detail of details) {
    const location = Array.isArray(detail?.loc) ? detail.loc : []
    const fields = location.filter(
      (part, index) =>
        typeof part === 'string' && !(index === 0 && ['body', 'query', 'path'].includes(part))
    )
    const field = fields.at(-1)
    if (!field) continue
    const message = `${fieldLabel(field, requestUrl)}：${safeDetailMessage(detail)}`
    if (!seen.has(message)) {
      seen.add(message)
      messages.push(message)
    }
  }
  if (!messages.length) return payload?.msg || '请求未完成，请检查填写内容后重试'
  const visible = messages.slice(0, 3)
  const remaining = messages.length - visible.length
  return `${visible.join('；')}${remaining > 0 ? `；另有 ${remaining} 项请检查` : ''}`
}

export function shouldShowLocalError(error) {
  return error?.notified !== true
}

export async function readErrorPayload(data) {
  if (!data) return null
  if (typeof data === 'object' && typeof data.text !== 'function') return data
  try {
    const text = typeof data.text === 'function' ? await data.text() : String(data)
    return text ? JSON.parse(text) : null
  } catch {
    return null
  }
}
