import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')
const sha256 = (path) => createHash('sha256').update(read(path)).digest('hex').toUpperCase()

test('管理员与工作台顶部壳严格使用各自权限来源', () => {
  const admin = read('web/src/layout/index.vue')
  const work = read('web/src/layout/work/index.vue')

  assert.match(admin, /PortalTopBar/)
  assert.match(admin, /permissionStore\.menus/)
  assert.match(admin, /buildAdminMenuModels/)
  assert.doesNotMatch(admin, /permissionStore\.accessApis/)

  assert.match(work, /PortalTopBar/)
  assert.match(work, /permissionStore\.accessApis/)
  assert.match(work, /buildWorkMenuModels/)
  assert.doesNotMatch(work, /permissionStore\.menus/)
})

test('桌面横向菜单与移动抽屉复用同一模型并在路由变化后关闭', () => {
  const menu = read('web/src/layout/components/topnav/ResponsiveTopMenu.vue')

  assert.match(menu, /mode="horizontal"/)
  assert.match(menu, /responsive/)
  assert.match(menu, /n-drawer/)
  assert.match(menu, /menuModels/)
  assert.match(menu, /route\.fullPath/)
  assert.match(menu, /drawerOpen\.value\s*=\s*false/)
  assert.doesNotMatch(menu, /v-html/)
})

test('头部动作保留业务组件并按 portal 传个人中心路径', () => {
  const actions = read('web/src/layout/components/header/HeaderActions.vue')
  const avatar = read('web/src/layout/components/header/components/UserAvatar.vue')

  for (const component of ['NotificationBell', 'Languages', 'ThemeMode', 'FullScreen', 'UserAvatar']) {
    assert.match(actions, new RegExp(component))
  }
  assert.doesNotMatch(actions, /MenuCollapse|BreadCrumb/)
  assert.match(actions, /profilePath/)
  assert.match(avatar, /default:\s*['"]\/profile['"]/)
  assert.match(avatar, /router\.push\(props\.profilePath\)/)
})

test('头部交互触发器自身具备 40px 热区、键盘语义与可读标签', () => {
  const components = {
    language: read('web/src/layout/components/header/components/Languages.vue'),
    theme: read('web/src/layout/components/header/components/ThemeMode.vue'),
    avatar: read('web/src/layout/components/header/components/UserAvatar.vue'),
  }

  for (const [name, source] of Object.entries(components)) {
    assert.match(source, /<button\b[\s\S]*?aria-label=/, name)
    assert.match(source, /min-width:\s*40px/, name)
    assert.match(source, /min-height:\s*40px/, name)
    assert.match(source, /:focus-visible/, name)
  }
})

test('深色顶部栏动作使用专用半透明交互底色而非浅色页面表面', () => {
  const shell = read('web/src/styles/app-shell.scss')
  const paths = [
    'web/src/layout/components/header/components/Languages.vue',
    'web/src/layout/components/header/components/ThemeMode.vue',
    'web/src/layout/components/header/components/UserAvatar.vue',
    'web/src/layout/components/header/components/NotificationBell.vue',
    'web/src/layout/components/header/components/FullScreen.vue',
  ]

  assert.match(shell, /--topbar-action-hover:\s*rgba\(/)
  for (const path of paths) assert.match(read(path), /var\(--topbar-action-hover/)
})

test('移动端品牌首页链接保留至少 40px 点击热区', () => {
  const source = read('web/src/layout/components/topnav/TopBrand.vue')

  assert.match(source, /\.top-brand\s*\{[\s\S]*?min-height:\s*40px/)
  assert.match(source, /aria-label=/)
})

test('通知面板只使用主题变量呈现边框、表面与正文颜色', () => {
  const source = read('web/src/layout/components/header/components/NotificationBell.vue')

  assert.doesNotMatch(source, /#(?:eee|f5f5f5|f5f7fa|f0f7ff|666|aaa|999)\b/i)
  for (const token of ['--shell-border', '--shell-surface-muted', '--shell-accent-soft', '--shell-text', '--shell-text-muted']) {
    assert.match(source, new RegExp(token))
  }
})

test('AppMain 保持单实例且不按断点重建', () => {
  for (const path of ['web/src/layout/index.vue', 'web/src/layout/work/index.vue']) {
    const source = read(path)
    assert.equal((source.match(/<AppMain\b/g) || []).length, 1, path)
    assert.doesNotMatch(source, /<AppMain[^>]*(:key|v-if|v-else)/)
  }
})

test('portal、守卫、路由、权限与 KeepAlive 真值文件保持实施前哈希', () => {
  const expected = {
    'web/src/utils/portal.js': 'D5F117A8A22669869730404AAC50B1D9AB1E7C7D31B3310F1D9533023CD11750',
    'web/src/router/guard/auth-guard.js': '7B2C7494F9802691AB6F9FD372C07A288DE14F79FB82F1DA0246CF285A0F8D7D',
    'web/src/router/routes/index.js': '8978C7BEFE7AC4533429B87D1A9CD9F5B55BF458D68B31555955F5033AEE5EDE',
    'web/src/store/modules/permission/index.js': '3A28A1C452E6B402282289B5F80C22A20B35BF0C08FAB2D43C3350B9A2EA74A0',
    'web/src/layout/components/AppMain.vue': 'EA030470BE72961C32F257451C12D0FF407B31B073EDFC8FE708B1C4AD84E8CC',
  }

  for (const [path, hash] of Object.entries(expected)) assert.equal(sha256(path), hash, path)
})
