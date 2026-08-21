import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const html = readFileSync(
  new URL('../../../web/index.html', import.meta.url),
  'utf8',
)
const css = readFileSync(
  new URL('../../../web/public/resource/loading.css', import.meta.url),
  'utf8',
)
const script = readFileSync(
  new URL('../../../web/public/resource/loading.js', import.meta.url),
  'utf8',
)

test('访问加载态把同源 Logo、spinner 和标题放在同一内容容器内', () => {
  assert.match(
    html,
    /<div\s+class="loading-container"[^>]*>\s*<div\s+class="loading-content"[^>]*role="status"[^>]*aria-live="polite"[^>]*>\s*<img\s+[^>]*id="loadingLogo"[^>]*class="loading-logo"[^>]*src="\/resource\/company-logo\.jpg"[^>]*>\s*<div\s+class="loading-spin__container"[^>]*>[\s\S]*?<div\s+class="loading-title"><%= title %><\/div>\s*<\/div>\s*<\/div>/,
  )
  assert.doesNotMatch(html, /(?:src|href)="(?:https?:)?\/\//i)
})

test('访问加载态以 grid 和单一中心轴居中内容', () => {
  assert.match(
    css,
    /\.loading-container\s*\{[\s\S]*?position:\s*fixed;[\s\S]*?inset:\s*0;[\s\S]*?display:\s*grid;[\s\S]*?place-items:\s*center;/,
  )
  assert.match(
    css,
    /\.loading-content\s*\{[\s\S]*?display:\s*flex;[\s\S]*?flex-direction:\s*column;[\s\S]*?align-items:\s*center;[\s\S]*?text-align:\s*center;/,
  )
  assert.doesNotMatch(
    css,
    /\.loading-spin__container\s*\{[\s\S]*?margin:\s*[^;]*auto\s+\d/,
  )
})

test('主题色只在 CSS 校验通过后使用 setProperty 写入', () => {
  assert.doesNotMatch(script, /innerHTML|style\.cssText/)
  assert.match(script, /CSS\.supports\(\s*['"]color['"]\s*,\s*themeColor\s*\)/)
  assert.match(
    script,
    /document\.documentElement\.style\.setProperty\(\s*['"]--primary-color['"]\s*,\s*themeColor\s*\)/,
  )
})

test('减少动态效果偏好会停止加载动画', () => {
  assert.match(css, /@media\s*\(prefers-reduced-motion:\s*reduce\)/)
  assert.match(
    css,
    /@media\s*\(prefers-reduced-motion:\s*reduce\)\s*\{[\s\S]*?\.loading-spin[\s\S]*?animation:\s*none;/,
  )
})
