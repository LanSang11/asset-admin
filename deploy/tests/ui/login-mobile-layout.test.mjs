import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const css = readFileSync(
  new URL('../../../web/src/views/login/login-theme.css', import.meta.url),
  'utf8'
)

function rule(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const matches = [...css.matchAll(new RegExp(`${escaped}\\s*\\{([\\s\\S]*?)\\}`, 'g'))]
  assert.ok(matches.length, `missing CSS rule: ${selector}`)
  return matches.map((match) => match[1]).join('\n')
}

test('mobile login owns a dynamic-height scroll container instead of relying on the locked body', () => {
  const root = rule('.login-root')

  assert.match(root, /(?:^|\n)\s*height:\s*100vh\s*;/)
  assert.match(root, /(?:^|\n)\s*height:\s*100dvh\s*;/)
  assert.match(root, /min-height:\s*0\s*;/)
  assert.match(root, /overflow-y:\s*auto\s*;/)
  assert.match(root, /-webkit-overflow-scrolling:\s*touch\s*;/)
})

test('mobile login keeps the submit action above the browser and device safe area', () => {
  const content = rule('.login-content')
  const submit = rule('.login-field--submit')

  assert.match(content, /min-height:\s*100%\s*;/)
  assert.match(content, /env\(safe-area-inset-bottom\)/)
  assert.match(submit, /bottom:\s*calc\(12px\s*\+\s*env\(safe-area-inset-bottom\)\)\s*;/)
})
