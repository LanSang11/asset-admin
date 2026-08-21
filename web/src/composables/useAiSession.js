import { ref } from 'vue'

function createId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID()
  return `s-${Date.now()}`
}

const open = ref(false)
const sending = ref(false)
const sessionId = ref(createId())
const messages = ref([
  {
    role: 'assistant',
    content:
      '我是只读助手。先查你权限内的资产、流转和知识库，再用你配置的 DeepSeek 说成人话（默认关闭深度思考）。安全数据只对超级管理员开放。',
    cards: [],
  },
])

export function useAiSession() {
  function toggle() {
    open.value = !open.value
  }

  function append(message) {
    messages.value = [...messages.value, message]
  }

  return {
    open,
    sending,
    sessionId,
    messages,
    toggle,
    append,
  }
}
