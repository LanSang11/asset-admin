import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, resolve } from 'node:path'

const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), '../../..')
const read = (path) => readFileSync(resolve(repoRoot, path), 'utf8')

test('管理端与工作台同一 40px AI 触发器', () => {
  const actions = read('web/src/layout/components/header/HeaderActions.vue')
  const trigger = read('web/src/components/ai/AiAssistantTrigger.vue')
  const drawer = read('web/src/components/ai/AiAssistantDrawer.vue')

  assert.match(actions, /AiAssistantTrigger/)
  assert.match(trigger, /min-width:\s*40px/)
  assert.match(trigger, /min-height:\s*40px/)
  assert.match(trigger, /aria-label=/)
  assert.match(drawer, /askAssistant|assistant\/ask/)
  assert.match(drawer, /思考已关/)
  assert.doesNotMatch(drawer, /v-html|system\s*:/)
  assert.match(drawer, /route_name/)
  assert.match(drawer, /entity_type/)
  assert.match(drawer, /entity_id/)
  assert.match(drawer, /filter_id/)
})

test('短会话不随路由清空且失败不影响业务页', () => {
  const session = read('web/src/composables/useAiSession.js')
  const drawer = read('web/src/components/ai/AiAssistantDrawer.vue')
  assert.match(session, /sessionId/)
  assert.doesNotMatch(session, /onBeforeRouteLeave[\s\S]*messages\.value\s*=\s*\[\]/)
  assert.match(drawer, /catch/)
  assert.doesNotMatch(drawer, /logout\(/)
  assert.doesNotMatch(drawer, /(?<!sessionId)session\./)
})
