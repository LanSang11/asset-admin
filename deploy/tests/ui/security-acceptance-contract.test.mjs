import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('安全中心有限时验收模式：开启要动态码，关闭不改高危策略', () => {
  const page = read('web/src/views/system/security/index.vue')
  assert.match(page, /限时验收模式/)
  assert.match(page, /acceptance_mode_update/)
  assert.match(page, /updateAcceptanceMode\(\{ enabled: true \}/)
  assert.match(page, /updateAcceptanceMode\(\{ enabled: false \}/)
  assert.match(page, /逐项验证和根保护/)
  assert.doesNotMatch(page, /关[闭掉]二次验证/)
})

test('安全中心可查看 HTTPS 证书并点续签', () => {
  const page = read('web/src/views/system/security/index.vue')
  const api = read('web/src/api/index.js')
  assert.match(page, /HTTPS 证书/)
  assert.match(page, /tls_cert_renew/)
  assert.match(page, /renewTlsCert/)
  assert.match(page, /到期时间/)
  assert.match(api, /\/security\/tls/)
})

test('管理壳在开启验收模式时显示到期横幅', () => {
  const layout = read('web/src/layout/index.vue')
  const banner = read('web/src/layout/components/AcceptanceModeBanner.vue')
  assert.match(layout, /AcceptanceModeBanner/)
  assert.match(banner, /acceptance_mode/)
  assert.match(banner, /到期自动恢复/)
})
