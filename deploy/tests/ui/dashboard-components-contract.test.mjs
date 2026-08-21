import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('方案 2 样式暴露统一尺寸、暗色与减弱动画 token', () => {
  const css = read('web/src/styles/app-shell.scss')
  const main = read('web/src/main.js')

  assert.match(main, /@\/styles\/app-shell\.scss/)
  assert.match(css, /--shell-header-height:\s*72px/)
  assert.match(css, /--shell-routebar-height:\s*48px/)
  assert.match(css, /--nav-icon-size:\s*20px/)
  assert.match(css, /--action-hit-size:\s*40px/)
  assert.match(css, /--surface-radius:\s*10px/)
  assert.match(css, /\.dark[\s\S]*--shell-bg:/)
  assert.match(css, /@media\s*\(max-width:\s*767px\)/)
  assert.match(css, /prefers-reduced-motion:\s*reduce/)
  assert.match(css, /\.portal-topbar__nav[\s\S]*min-width:\s*0/)
})

test('共享看板组件保持纯展示且不使用 HTML 注入', () => {
  const metric = read('web/src/components/dashboard/MetricCard.vue')
  const panel = read('web/src/components/dashboard/DashboardPanel.vue')
  const trend = read('web/src/components/dashboard/TrendBars.vue')

  for (const source of [metric, panel, trend]) {
    assert.doesNotMatch(source, /@\/api|use[A-Z]\w*Store|v-html/)
  }
  for (const prop of ['label', 'value', 'hint', 'tone', 'badge']) assert.match(metric, new RegExp(`\\b${prop}\\b`))
  assert.match(panel, /name="action"/)
  assert.match(panel, /<slot\s*\/>/)
  assert.match(trend, /aria-label/)
  assert.match(trend, /getTrendMax/)
  assert.match(trend, /getTrendBarHeight/)
  assert.doesNotMatch(trend, /Math\.max\(2/)
  assert.doesNotMatch(trend, /min-height:\s*2px/)
})

test('AppPage 与 CommonPage 保留滚动、footer、back-top 和业务插槽', () => {
  const appPage = read('web/src/components/page/AppPage.vue')
  const commonPage = read('web/src/components/page/CommonPage.vue')

  assert.match(appPage, /class="[^"]*app-page/)
  assert.match(appPage, /cus-scroll-y/)
  assert.match(appPage, /AppFooter\s+v-if="showFooter"/)
  assert.match(appPage, /n-back-top/)
  assert.match(commonPage, /class="[^"]*common-page/)
  assert.match(commonPage, /name="header"/)
  assert.match(commonPage, /name="action"/)
  assert.match(commonPage, /<slot\s*\/>/)
})
