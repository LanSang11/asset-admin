<template>
  <n-drawer v-model:show="open" :width="drawerWidth" placement="right">
    <n-drawer-content title="只读助手" closable>
      <div class="ai-drawer">
        <div class="ai-drawer__log" aria-live="polite">
          <article v-for="(item, index) in messages" :key="index" class="ai-msg" :data-role="item.role">
            <p class="ai-msg__text">{{ item.content }}</p>
            <p v-if="item.source === 'model'" class="ai-msg__meta">已用你配置的模型作答（思考已关）</p>
            <p v-else-if="item.source === 'facts'" class="ai-msg__meta">未调用模型，以上是系统查到的事实</p>
            <ul v-if="item.cards?.length" class="ai-cards">
              <li v-for="card in item.cards" :key="card.alias">
                <strong>{{ card.alias }}</strong>
                <span>{{ cardLabel(card) }}</span>
              </li>
            </ul>
          </article>
        </div>
        <form class="ai-drawer__form" @submit.prevent="send">
          <textarea
            v-model="draft"
            rows="3"
            maxlength="2000"
            placeholder="问本页怎么用、操作说明，或你权限内的资产 / 流转"
            :disabled="sending"
          />
          <button type="submit" :disabled="sending || !draft.trim()">发送</button>
        </form>
      </div>
    </n-drawer-content>
  </n-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { NDrawer, NDrawerContent } from 'naive-ui'
import api from '@/api'
import { useAiSession } from '@/composables/useAiSession'

const { open, sending, sessionId, messages, append } = useAiSession()
const route = useRoute()
const draft = ref('')
const drawerWidth = computed(() => (typeof window !== 'undefined' && window.innerWidth < 768 ? '100%' : 400))

function pageContext() {
  return {
    route_name: String(route.name || route.meta?.title || ''),
    entity_type: String(route.meta?.entityType || inferEntity(route.path)),
    entity_id: String(route.params?.id || route.query?.id || ''),
    filter_id: String(route.query?.filter_id || ''),
  }
}

function inferEntity(path) {
  if (String(path).includes('asset')) return 'asset'
  if (String(path).includes('employee')) return 'employee'
  return ''
}

function cardLabel(card) {
  if (card.kind === 'asset') return `${card.asset_no || ''} ${card.name || ''}`.trim()
  if (card.kind === 'person') return card.name || ''
  if (card.kind === 'ip') return card.ip || ''
  if (card.kind === 'filter') return card.tab || ''
  if (card.kind === 'kb') return `《${card.name || ''}》${card.snippet || ''}`
  return card.alias || ''
}

async function send() {
  const text = draft.value.trim()
  if (!text || sending.value) return
  draft.value = ''
  append({ role: 'user', content: text, cards: [] })
  sending.value = true
  try {
    const res = await api.askAssistant({
      user_text: text,
      session_id: sessionId.value,
      page_context: pageContext(),
      channel: 'system',
    })
    append({
      role: 'assistant',
      content: res?.data?.text || res?.msg || '没有返回内容',
      cards: res?.data?.cards || [],
      source: res?.data?.source || '',
    })
  } catch (error) {
    append({
      role: 'assistant',
      content: error?.message || '助手暂时不可用，请直接使用页面功能。',
      cards: [],
    })
  } finally {
    sending.value = false
  }
}
</script>

<style scoped>
.ai-drawer {
  display: flex;
  height: 100%;
  min-height: 360px;
  flex-direction: column;
  gap: 12px;
}
.ai-drawer__log {
  display: flex;
  min-height: 0;
  flex: 1;
  flex-direction: column;
  gap: 10px;
  overflow: auto;
}
.ai-msg {
  padding: 10px 12px;
  border-radius: 10px;
  background: var(--shell-surface-muted, #f5f7fa);
}
.ai-msg[data-role='user'] {
  background: var(--shell-accent-soft, #e8f1ff);
}
.ai-msg__text {
  margin: 0;
  color: var(--shell-text);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.6;
}
.ai-msg__meta {
  margin: 6px 0 0;
  color: var(--shell-text-muted, #667085);
  font-size: 11px;
}
.ai-cards {
  display: flex;
  margin: 8px 0 0;
  padding: 0;
  flex-direction: column;
  gap: 4px;
  list-style: none;
  color: var(--shell-text-muted);
  font-size: 12px;
}
.ai-drawer__form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-drawer__form textarea {
  width: 100%;
  padding: 8px;
  border: 1px solid var(--shell-border);
  border-radius: 8px;
  resize: vertical;
  color: var(--shell-text);
  background: var(--shell-surface);
}
.ai-drawer__form button {
  min-height: 40px;
  border: 0;
  border-radius: 8px;
  color: #fff;
  background: var(--shell-accent);
  cursor: pointer;
}
.ai-drawer__form button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
</style>
