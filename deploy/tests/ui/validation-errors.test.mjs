import test from 'node:test'
import assert from 'node:assert/strict'

const validationErrors = await import('../../../web/src/utils/http/validation-errors.js').catch(() => ({}))
const formValidation = await import('../../../web/src/utils/form-validation.js').catch(() => ({}))

test('422 详情按业务字段生成用户看得懂的中文提示', () => {
  assert.equal(typeof validationErrors.formatValidationMessage, 'function')

  const message = validationErrors.formatValidationMessage(
    {
      code: 422,
      msg: '提交内容有误，请按提示修改',
      data: [
        {
          loc: ['body', 'new_password'],
          msg: '密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号',
          type: 'value_error',
        },
      ],
    },
    '/api/v1/base/update_password',
  )

  assert.equal(message, '新密码：密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号')
})

test('同一请求聚合最多三条字段错误并去重', () => {
  assert.equal(typeof validationErrors.formatValidationMessage, 'function')

  const message = validationErrors.formatValidationMessage(
    {
      code: 422,
      data: [
        { loc: ['body', 'asset_no'], msg: '不能为空', type: 'missing' },
        { loc: ['body', 'name'], msg: '最多输入 100 个字符', type: 'string_too_long' },
        { loc: ['body', 'price'], msg: '需大于或等于 0', type: 'greater_than_equal' },
        { loc: ['body', 'remark'], msg: '最多输入 255 个字符', type: 'string_too_long' },
        { loc: ['body', 'asset_no'], msg: '不能为空', type: 'missing' },
      ],
    },
    '/api/v1/asset/create',
  )

  assert.equal(
    message,
    '资产编号：不能为空；资产名称：最多输入 100 个字符；采购价格：需大于或等于 0；另有 1 项请检查',
  )
})

test('错误格式化不读取或回显请求输入值', () => {
  assert.equal(typeof validationErrors.formatValidationMessage, 'function')

  const secret = 'Fixture!Secret9'
  const message = validationErrors.formatValidationMessage(
    {
      code: 422,
      msg: '提交内容有误，请按提示修改',
      data: [
        {
          loc: ['body', 'password'],
          msg: '填写内容不符合要求',
          type: 'value_error',
          input: secret,
        },
      ],
    },
    '/api/v1/user/create',
  )

  assert.equal(message, '密码：填写内容不符合要求')
  assert.equal(message.includes(secret), false)
})

test('无字段详情时保留后端业务提示', () => {
  assert.equal(typeof validationErrors.formatValidationMessage, 'function')
  assert.equal(
    validationErrors.formatValidationMessage({ code: 409, msg: '用户名称已存在' }, '/api/v1/user/create'),
    '用户名称已存在',
  )
})

test('API 管理与盘点使用各自业务字段名', () => {
  assert.equal(
    validationErrors.formatValidationMessage(
      { code: 422, data: [{ loc: ['body', 'path'], msg: '最多输入 100 个字符' }] },
      '/api/v1/api/create',
    ),
    'API 路径：最多输入 100 个字符',
  )
  assert.equal(
    validationErrors.formatValidationMessage(
      { code: 422, data: [{ loc: ['body', 'note'], msg: '最多输入 255 个字符' }] },
      '/api/v1/inventory/start',
    ),
    '备注：最多输入 255 个字符',
  )
})

test('全局拦截器已提示的错误由页面跳过重复弹窗', () => {
  assert.equal(typeof validationErrors.shouldShowLocalError, 'function')
  assert.equal(validationErrors.shouldShowLocalError({ notified: true }), false)
  assert.equal(validationErrors.shouldShowLocalError({ notified: false }), true)
  assert.equal(validationErrors.shouldShowLocalError(new Error('本地操作失败')), true)
})

test('下载接口返回 JSON Blob 时可提取同一错误契约', async () => {
  assert.equal(typeof validationErrors.readErrorPayload, 'function')

  const payload = await validationErrors.readErrorPayload(
    new Blob([JSON.stringify({ code: 422, msg: '导出条件有误，请检查筛选项' })], {
      type: 'application/json',
    }),
  )

  assert.deepEqual(payload, { code: 422, msg: '导出条件有误，请检查筛选项' })
})

test('密码表单复用与后端一致的强度规则和引导文案', () => {
  assert.equal(typeof formValidation.isStrongPassword, 'function')
  assert.equal(
    formValidation.PASSWORD_RULE_TEXT,
    '密码需 8~32 位且包含大写字母、小写字母、数字、特殊符号',
  )
  assert.equal(formValidation.isStrongPassword('FxA!k9Qm2pL'), true)
  assert.equal(formValidation.isStrongPassword('lowercase!9'), false)
  assert.equal(formValidation.isStrongPassword('UPPERCASE!9'), false)
  assert.equal(formValidation.isStrongPassword('NoNumber!'), false)
  assert.equal(formValidation.isStrongPassword('NoSpecial9'), false)
})
