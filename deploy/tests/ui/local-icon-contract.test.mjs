import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('动态图标使用离线渲染器且未知名称回退到本地图标', async () => {
  const source = read('web/src/utils/common/icon.js')
  assert.match(source, /@iconify\/vue\/offline/)
  assert.doesNotMatch(source, /from ['"]@iconify\/vue['"]/)
  assert.match(source, /resolveLocalIcon/)

  const registryUrl = pathToFileURL(resolve(repoRoot, 'web/src/utils/common/local-icon-data.js'))
  const { resolveLocalIcon } = await import(registryUrl.href)
  const known = resolveLocalIcon('mdi:desktop-classic')
  const fallback = resolveLocalIcon('missing:fixture')
  assert.equal(typeof known?.body, 'string')
  assert.ok(known.body.length > 0)
  assert.deepEqual(fallback, resolveLocalIcon('mdi:shape-outline'))
})

test('图标选择器现有本地候选全部可离线解析', async () => {
  const pickerNames = [...read('web/src/assets/js/icons.js').matchAll(/'([^']+)'/g)].map(
    ([, name]) => name.replace(/^mdi-/, 'mdi:')
  )
  const registryUrl = pathToFileURL(resolve(repoRoot, 'web/src/utils/common/local-icon-data.js'))
  const { hasLocalIcon } = await import(registryUrl.href)
  assert.ok(pickerNames.length > 200)
  for (const name of pickerNames) assert.equal(hasLocalIcon(name), true, name)
})

test('最终门禁扫描构建产物中的 Iconify 运行时 API 域名', () => {
  const source = read('deploy/tools/assert_ui_option2.mjs')
  for (const domain of ['api.iconify.design', 'api.simplesvg.com', 'api.unisvg.com']) {
    assert.match(source, new RegExp(domain.replaceAll('.', '\\.')))
  }
  assert.match(source, /dist[\s\S]*forbiddenRuntimeDomains/)
})
