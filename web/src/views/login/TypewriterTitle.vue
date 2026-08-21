<template>
  <h1 class="typewriter-title" :aria-label="text">
    <span class="typewriter-text">{{ displayText }}</span>
    <span
      v-if="showCaret"
      class="typewriter-caret"
      :class="{ 'is-blink': phase === 'hold' || reducedMotion }"
      aria-hidden="true"
    />
  </h1>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = defineProps({
  /** 标题全文：写死/配置常量，禁止 v-html 用户输入 */
  text: {
    type: String,
    default: '资产管理系统',
  },
  /** 每字打出间隔 ms */
  speed: {
    type: Number,
    default: 90,
  },
  /** 每字删除间隔 ms（循环回退） */
  deleteSpeed: {
    type: Number,
    default: 45,
  },
  /** 开场延迟 ms */
  startDelay: {
    type: Number,
    default: 280,
  },
  /** 打完后停留 ms，再开始删除 */
  holdDelay: {
    type: Number,
    default: 1800,
  },
  /** 删完后到下一轮打字的间隔 ms */
  loopGap: {
    type: Number,
    default: 420,
  },
  /** 是否循环；reduced-motion 时强制关闭 */
  loop: {
    type: Boolean,
    default: true,
  },
})

const reducedMotion = ref(false)
const index = ref(0)
/** typing | hold | deleting | idle */
const phase = ref('idle')

let timer = 0
let startTimer = 0
let holdTimer = 0
let gapTimer = 0

const displayText = computed(() => {
  if (reducedMotion.value) return props.text
  return props.text.slice(0, index.value)
})

const showCaret = computed(() => {
  if (reducedMotion.value) return false
  return true
})

function clearTimers() {
  if (timer) {
    clearInterval(timer)
    timer = 0
  }
  if (startTimer) {
    clearTimeout(startTimer)
    startTimer = 0
  }
  if (holdTimer) {
    clearTimeout(holdTimer)
    holdTimer = 0
  }
  if (gapTimer) {
    clearTimeout(gapTimer)
    gapTimer = 0
  }
}

function showFullStatic() {
  clearTimers()
  index.value = props.text.length
  phase.value = 'hold'
}

function beginDelete() {
  phase.value = 'deleting'
  if (timer) {
    clearInterval(timer)
    timer = 0
  }
  timer = window.setInterval(() => {
    if (index.value <= 0) {
      clearInterval(timer)
      timer = 0
      phase.value = 'idle'
      // 下一轮
      gapTimer = window.setTimeout(() => {
        beginTyping(false)
      }, Math.max(0, props.loopGap))
      return
    }
    index.value -= 1
  }, Math.max(20, props.deleteSpeed))
}

function beginTyping(withStartDelay) {
  clearTimers()
  phase.value = 'typing'
  index.value = 0

  if (reducedMotion.value || !props.text) {
    showFullStatic()
    return
  }

  const delay = withStartDelay ? Math.max(0, props.startDelay) : 0
  startTimer = window.setTimeout(() => {
    timer = window.setInterval(() => {
      if (index.value >= props.text.length) {
        clearInterval(timer)
        timer = 0
        phase.value = 'hold'
        if (props.loop && !reducedMotion.value) {
          holdTimer = window.setTimeout(() => {
            beginDelete()
          }, Math.max(0, props.holdDelay))
        }
        return
      }
      index.value += 1
    }, Math.max(30, props.speed))
  }, delay)
}

function startTyping() {
  beginTyping(true)
}

function detectReduce() {
  if (typeof window === 'undefined' || !window.matchMedia) {
    reducedMotion.value = false
    return
  }
  reducedMotion.value = window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

let mq = null
function onMqChange(e) {
  reducedMotion.value = !!e.matches
  startTyping()
}

onMounted(() => {
  detectReduce()
  if (typeof window !== 'undefined' && window.matchMedia) {
    mq = window.matchMedia('(prefers-reduced-motion: reduce)')
    if (mq.addEventListener) mq.addEventListener('change', onMqChange)
    else if (mq.addListener) mq.addListener(onMqChange)
  }
  startTyping()
})

onBeforeUnmount(() => {
  clearTimers()
  if (mq) {
    if (mq.removeEventListener) mq.removeEventListener('change', onMqChange)
    else if (mq.removeListener) mq.removeListener(onMqChange)
  }
})

watch(
  () => [props.text, props.loop, props.speed, props.deleteSpeed, props.holdDelay],
  () => startTyping(),
)
</script>

<style scoped>
.typewriter-title {
  margin: 0;
  padding: 0;
  font-size: 22px;
  font-weight: 600;
  letter-spacing: 0.12em;
  line-height: 1.4;
  color: var(--yd-text, #e2e8f0);
  text-align: center;
  min-height: 1.4em;
  font-family:
    'Segoe UI',
    system-ui,
    -apple-system,
    'PingFang SC',
    'Microsoft YaHei',
    sans-serif;
}

.typewriter-text {
  background: linear-gradient(
    120deg,
    #e2e8f0 0%,
    #7dd3fc 45%,
    #22d3ee 100%
  );
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}

@supports not (background-clip: text) {
  .typewriter-text {
    color: var(--yd-text, #e2e8f0);
    background: none;
  }
}

.typewriter-caret {
  display: inline-block;
  width: 2px;
  height: 1.05em;
  margin-left: 3px;
  vertical-align: -0.12em;
  background: var(--yd-accent, #38bdf8);
  border-radius: 1px;
  opacity: 0.9;
}

.typewriter-caret.is-blink {
  animation: yd-caret-blink 1s steps(1) infinite;
}

@keyframes yd-caret-blink {
  0%,
  50% {
    opacity: 0.95;
  }
  50.01%,
  100% {
    opacity: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .typewriter-caret {
    display: none;
  }
}
</style>
