import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('登录第二步：密码通过后出 6 位框，拦截器不弹红字失败', () => {
  const login = read('web/src/views/login/index.vue')
  const interceptors = read('web/src/utils/http/interceptors.js')
  assert.match(login, /密码已通过/)
  assert.match(login, /totp_challenge/)
  assert.match(login, /验证并登录/)
  const submitAt = login.indexOf('验证并登录')
  const downloadAt = login.indexOf('AuthenticatorDownloadLinks')
  assert.ok(submitAt > 0 && downloadAt > submitAt, '下载链接必须在登录按钮之后，避免挤掉按钮')
  assert.match(login, /login-auth-dl/)
  assert.doesNotMatch(login, /\/user\/totp-status/)
  assert.match(interceptors, /isTotpChallenge/)
  assert.match(interceptors, /totp_challenge/)
})

test('AI 预设默认 deepseek-v4-flash，选厂商只补模型与地址', () => {
  const page = read('web/src/views/business/ai-assistant/index.vue')
  const presets = read('web/src/constants/aiPresets.js')
  assert.match(presets, /deepseek-v4-flash/)
  assert.match(presets, /api\.openai\.com\/v1/)
  assert.doesNotMatch(presets, /sk-[a-zA-Z0-9]{8,}/)
  assert.match(page, /applyAiPreset/)
  assert.match(page, /只读笼子/)
})

test('安全中心有默认关闭的到期换密', () => {
  const page = read('web/src/views/system/security/index.vue')
  assert.match(page, /到期换密（默认关闭）/)
  assert.match(page, /password_rotate/)
  assert.match(page, /password_max_days|max_days/)
})

test('个人中心首次进入落到二次验证向导，不是资料页', () => {
  const profile = read('web/src/views/profile/index.vue')
  assert.match(profile, /第一次绑定/)
  assert.match(profile, /isForceChange\.value \? 'contact' : 'totp'/)
  assert.doesNotMatch(profile, /isForceChange\.value \? 'contact' : 'website'/)
})

test('教程写清超管必须绑验证器，不教 SQL 关闭', () => {
  const guide = read('README-部署与使用教程.md')
  const readme = read('README.md')
  assert.match(guide, /绑定验证器/)
  assert.match(guide, /限时验收模式/)
  assert.match(guide, /不要用 SQL/)
  assert.match(readme, /不要用 SQL 去关二次验证/)
  assert.doesNotMatch(guide, /UPDATE\s+user\s+SET\s+totp_enabled/i)
})
