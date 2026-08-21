import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, extname, join, relative, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../..')
const uiTestRoot = resolve(repoRoot, 'deploy/tests/ui')
const webRoot = resolve(repoRoot, 'web')

function run(label, args) {
  process.stdout.write(`\n[UI-GATE] ${label}\n`)
  const result = spawnSync(process.execPath, args, { cwd: repoRoot, stdio: 'inherit' })
  if (result.error) throw result.error
  assert.equal(result.status, 0, `${label} exit ${result.status}`)
}

function walk(root) {
  return readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const path = join(root, entry.name)
    return entry.isDirectory() ? walk(path) : [path]
  })
}

function sha256(path) {
  return createHash('sha256').update(readFileSync(path)).digest('hex').toUpperCase()
}

const tests = readdirSync(uiTestRoot)
  .filter((name) => name.endsWith('.test.mjs'))
  .sort()
  .map((name) => resolve(uiTestRoot, name))

assert.ok(tests.length >= 6, `UI contract count too small: ${tests.length}`)
run('UI contract tests', ['--test', ...tests])
run('PORTAL-WB-1 prefix assertions', ['deploy/tools/assert_portal_prefix.mjs'])
run('notification route regex assertions', ['deploy/tools/verify_route_regex.mjs'])

assert.equal(
  sha256(resolve(webRoot, 'package.json')),
  '5702097407BEA52B4505F11A12CB36A66380258EA4E8AB39099F0FE97D81D923',
  'package.json changed',
)
assert.equal(
  sha256(resolve(webRoot, 'package-lock.json')),
  'A0753E258FF09465BB13F7D7A5AF4798FF76C3F291F2FC3D87732666976D8147',
  'package-lock.json changed',
)

const sourceFiles = [
  ...walk(resolve(webRoot, 'src')).filter((path) =>
    ['.js', '.ts', '.vue', '.html', '.css', '.scss'].includes(extname(path))
  ),
  resolve(webRoot, 'index.html'),
  resolve(webRoot, 'public/resource/loading.css'),
  resolve(webRoot, 'public/resource/loading.js'),
]
const forbidden = [
  [/\bv-html\s*=/, 'v-html'],
  [/\.innerHTML\s*=/, 'innerHTML assignment'],
  [/\.outerHTML\s*=/, 'outerHTML assignment'],
  [/\beval\s*\(/, 'eval'],
  [/\bnew\s+Function\b/, 'new Function'],
  [/javascript\s*:/i, 'javascript URL'],
]

for (const path of sourceFiles) {
  const source = readFileSync(path, 'utf8')
  for (const [pattern, label] of forbidden) {
    assert.doesNotMatch(source, pattern, `${label}: ${relative(repoRoot, path)}`)
  }
}

const html = readFileSync(resolve(webRoot, 'index.html'), 'utf8')
assert.doesNotMatch(html, /<(?:script|link)[^>]+(?:src|href)=["']https?:\/\//i, 'remote script/style')
const loadingScript = readFileSync(resolve(webRoot, 'public/resource/loading.js'), 'utf8')
assert.doesNotMatch(loadingScript, /innerHTML|style\.cssText/)
assert.match(loadingScript, /CSS\.supports/)
assert.match(loadingScript, /style\.setProperty/)

const distRoot = resolve(webRoot, 'dist')
const distFiles = walk(distRoot)
const forbiddenRuntimeDomains = ['api.iconify.design', 'api.simplesvg.com', 'api.unisvg.com']
const latestSourceMtime = Math.max(...sourceFiles.map((path) => statSync(path).mtimeMs))
const distIndexMtime = statSync(resolve(distRoot, 'index.html')).mtimeMs
assert.ok(
  distIndexMtime >= latestSourceMtime,
  'dist is older than production source; run npm build before the final UI gate'
)
assert.equal(distFiles.some((path) => path.endsWith('.map')), false, 'dist contains sourcemap')
const totalBytes = distFiles.reduce((sum, path) => sum + statSync(path).size, 0)
assert.ok(totalBytes <= 4_186_146, `dist unexpectedly doubled: ${totalBytes} bytes`)
for (const path of distFiles.filter((file) => file.endsWith('.js'))) {
  assert.ok(statSync(path).size <= 1_048_576, `chunk exceeds 1 MiB: ${relative(distRoot, path)}`)
}
for (const path of distFiles.filter((file) => ['.html', '.js', '.css'].includes(extname(file)))) {
  const output = readFileSync(path, 'utf8')
  for (const domain of forbiddenRuntimeDomains) {
    assert.equal(output.includes(domain), false, `runtime domain ${domain}: ${relative(distRoot, path)}`)
  }
}
const distHtml = readFileSync(resolve(distRoot, 'index.html'), 'utf8')
const entryMatch = distHtml.match(/(?:src|href)=["']\/assets\/(index-[^"']+\.js)/)
assert.ok(entryMatch, 'dist entry chunk missing')
const entryPath = resolve(distRoot, 'assets', entryMatch[1])
assert.ok(statSync(entryPath).size <= 813_512, `entry chunk exceeds baseline + 100 KiB: ${statSync(entryPath).size}`)

console.log(`\nUI OPTION 2 ALL PASS (${tests.length} contract files, dist ${totalBytes} bytes)`)
