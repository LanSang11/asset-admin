import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'
import { resolvePostLoginLocation } from '../../../web/src/utils/portal.js'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('站点根 redirect=/ 不得把管理员送进空白 RootPortal', () => {
  assert.equal(resolvePostLoginLocation('/', 'admin'), '/workbench')
  assert.equal(resolvePostLoginLocation('/', 'work'), '/work/home')
  assert.equal(resolvePostLoginLocation('/login', 'admin'), '/workbench')
  assert.equal(resolvePostLoginLocation('', 'admin'), '/workbench')
  assert.equal(resolvePostLoginLocation(undefined, 'admin'), '/workbench')
})

test('登录后保留合法深链，丢掉外链和员工不可进的管理路径', () => {
  assert.equal(resolvePostLoginLocation('/system/user', 'admin'), '/system/user')
  assert.deepEqual(
    resolvePostLoginLocation('/system/security?tab=login', 'admin'),
    { path: '/system/security', query: { tab: 'login' } },
  )
  assert.equal(resolvePostLoginLocation('/workbench', 'work'), '/work/home')
  assert.equal(resolvePostLoginLocation('/system/user', 'work'), '/work/home')
  assert.equal(resolvePostLoginLocation('/work/repair', 'work'), '/work/repair')
  assert.equal(resolvePostLoginLocation('https://example.com/phish', 'admin'), '/workbench')
  assert.equal(resolvePostLoginLocation('not-a-path', 'admin'), '/workbench')
})

test('登录页不再改写当前路由 query，也不再 push 站点根', () => {
  const login = read('web/src/views/login/index.vue')
  const guard = read('web/src/router/guard/auth-guard.js')
  const routes = read('web/src/router/routes/index.js')
  assert.match(login, /resolvePostLoginLocation/)
  assert.match(login, /leaveLogin/)
  assert.match(login, /router\.replace\(target\)/)
  assert.doesNotMatch(login, /Reflect\.deleteProperty/)
  assert.doesNotMatch(login, /const \{ query \} = useRoute\(\)/)
  assert.doesNotMatch(login, /router\.push\(\{ path, query \}\)/)
  assert.doesNotMatch(login, /router\.push\(home\)/)
  assert.match(guard, /path: '\/login'/)
  assert.doesNotMatch(guard, /path: 'login'/)
  assert.match(routes, /root-portal\.vue/)
  assert.doesNotMatch(routes, /render:\s*\(\)\s*=>\s*null/)
})
