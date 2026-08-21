/**
 * PORTAL-WB-1 回归：工作台前缀不得吞掉 /workbench；/ 不得写死管理端。
 * 用法：node deploy/tools/assert_portal_prefix.mjs
 */
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { canWorkUserAccessPath, getHomePath, isAdminLandingPath } from '../../web/src/utils/portal.js'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '../..')

const cases = [
  [canWorkUserAccessPath('/workbench'), false, "canWorkUserAccessPath('/workbench')"],
  [canWorkUserAccessPath('/workbench?x=1'), false, "canWorkUserAccessPath('/workbench?x=1')"],
  [canWorkUserAccessPath('/work'), true, "canWorkUserAccessPath('/work')"],
  [canWorkUserAccessPath('/work/home'), true, "canWorkUserAccessPath('/work/home')"],
  [canWorkUserAccessPath('/work/repair'), true, "canWorkUserAccessPath('/work/repair')"],
  [canWorkUserAccessPath('/system/user'), false, "canWorkUserAccessPath('/system/user')"],
  [canWorkUserAccessPath('/login'), true, "canWorkUserAccessPath('/login')"],
  [canWorkUserAccessPath('/profile'), true, "canWorkUserAccessPath('/profile')"],
  [canWorkUserAccessPath('/q/AST001'), true, "canWorkUserAccessPath('/q/AST001')"],
  [canWorkUserAccessPath('/q'), true, "canWorkUserAccessPath('/q')"],
  [getHomePath('work'), '/work/home', "getHomePath('work')"],
  [getHomePath('admin'), '/workbench', "getHomePath('admin')"],
  [isAdminLandingPath('/'), true, "isAdminLandingPath('/')"],
  [isAdminLandingPath('/workbench'), true, "isAdminLandingPath('/workbench')"],
  [isAdminLandingPath('/system/user'), false, "isAdminLandingPath('/system/user')"],
]

const portalSrc = readFileSync(join(root, 'web/src/utils/portal.js'), 'utf8')
const routesSrc = readFileSync(join(root, 'web/src/router/routes/index.js'), 'utf8')

const portalCode = portalSrc
  .split(/\r?\n/)
  .filter((line) => !/^\s*(\*|\/\/)/.test(line.trim().replace(/^\/\*/, '')))
  .join('\n')
cases.push([
  !/startsWith\(\s*['"]\/work['"]\s*\)/.test(portalCode),
  true,
  "portal.js 代码禁止 startsWith('/work') 无斜杠",
])
cases.push([
  /p === '\/work' \|\| p\.startsWith\('\/work\/'\)/.test(portalSrc),
  true,
  "portal.js 须用 === '/work' 或 startsWith('/work/')",
])
cases.push([
  !/redirect:\s*['"]\/workbench['"]/.test(routesSrc),
  true,
  "routes/index.js 禁止 redirect:'/workbench'",
])
cases.push([
  /path:\s*['"]\/['"][\s\S]{0,180}isHidden:\s*true/.test(routesSrc),
  true,
  "routes/index.js 站点根须 isHidden，避免侧栏出现 RootPortal",
])

let failed = 0
for (const [got, expect, name] of cases) {
  const ok = got === expect
  if (!ok) failed++
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name} -> ${JSON.stringify(got)} (expect ${JSON.stringify(expect)})`)
}
console.log(failed === 0 ? 'ALL PASS' : `${failed} FAILURES`)
process.exit(failed === 0 ? 0 : 1)
