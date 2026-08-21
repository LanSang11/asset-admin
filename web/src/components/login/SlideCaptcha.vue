<template>
  <div class="slide-captcha">
    <div class="slide-head">
      <span class="slide-title">安全验证</span>
      <button type="button" class="slide-refresh" :disabled="loading || verifying" @click="reload">刷新</button>
    </div>
    <div v-if="errorMsg" class="slide-err">{{ errorMsg }}</div>
    <div
      class="slide-panel"
      :style="{ width: bgWidth + 'px', height: bgHeight + 'px' }"
    >
      <img v-if="bg" class="slide-bg" :src="bg" alt="验证背景" draggable="false" />
      <img
        v-if="piece"
        class="slide-piece"
        :src="piece"
        alt=""
        draggable="false"
        :style="{ left: offsetX + 'px', top: pieceY + 'px', width: thumbWidth + 'px' }"
      />
      <div v-if="loading" class="slide-loading">加载中…</div>
    </div>
    <div
      ref="trackRef"
      class="slide-track"
      :style="{ width: bgWidth + 'px' }"
      @mousedown="onTrackDown"
      @touchstart.prevent="onTrackDown"
    >
      <div class="slide-track-fill" :style="{ width: Math.max(offsetX, 0) + 'px' }" />
      <div
        class="slide-btn"
        :class="{ active: dragging, ok: verified }"
        :style="{ left: offsetX + 'px' }"
      >
        {{ verifying ? '…' : verified ? '✓' : '››' }}
      </div>
      <span v-if="!dragging && !verified && !verifying" class="slide-hint">拖动滑块完成拼图</span>
    </div>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import api from '@/api'

const props = defineProps({
  /** 外部触发重新加载 */
  resetKey: { type: [Number, String], default: 0 },
})

const emit = defineEmits(['solved', 'cleared'])

const loading = ref(false)
const errorMsg = ref('')
const captchaId = ref('')
const bg = ref('')
const piece = ref('')
const pieceY = ref(0)
const bgWidth = ref(300)
const bgHeight = ref(150)
const thumbWidth = ref(42)
const offsetX = ref(0)
const dragging = ref(false)
const verified = ref(false)
const verifying = ref(false)
const trackRef = ref(null)

let startClientX = 0
let startOffset = 0
let challengeVersion = 0
const maxOffset = () => Math.max(0, bgWidth.value - thumbWidth.value)

async function reload() {
  const version = ++challengeVersion
  loading.value = true
  errorMsg.value = ''
  verified.value = false
  verifying.value = false
  offsetX.value = 0
  captchaId.value = ''
  emit('cleared')
  try {
    const res = await api.getSlideCaptcha()
    if (version !== challengeVersion) return
    const d = res.data || {}
    captchaId.value = d.captcha_id || ''
    bg.value = d.bg_base64 || ''
    piece.value = d.piece_base64 || ''
    pieceY.value = d.y || 0
    bgWidth.value = d.bg_width || 300
    bgHeight.value = d.bg_height || 150
    thumbWidth.value = d.thumb_width || 42
  } catch (e) {
    if (version !== challengeVersion) return
    errorMsg.value = e?.message || '验证码加载失败'
  } finally {
    if (version === challengeVersion) loading.value = false
  }
}

function clientX(e) {
  if (e.touches && e.touches[0]) return e.touches[0].clientX
  if (e.changedTouches && e.changedTouches[0]) return e.changedTouches[0].clientX
  return e.clientX
}

function onTrackDown(e) {
  if (loading.value || verifying.value || verified.value || !captchaId.value) return
  dragging.value = true
  verified.value = false
  startClientX = clientX(e)
  startOffset = offsetX.value
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
  window.addEventListener('touchmove', onMove, { passive: false })
  window.addEventListener('touchend', onUp)
}

function onMove(e) {
  if (!dragging.value) return
  if (e.cancelable) e.preventDefault()
  const dx = clientX(e) - startClientX
  let next = startOffset + dx
  next = Math.max(0, Math.min(maxOffset(), next))
  offsetX.value = next
}

async function onUp() {
  if (!dragging.value) return
  dragging.value = false
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  window.removeEventListener('touchmove', onMove)
  window.removeEventListener('touchend', onUp)
  verifying.value = true
  errorMsg.value = ''
  const submittedId = captchaId.value
  const submittedX = Math.round(offsetX.value)
  const submittedVersion = challengeVersion
  try {
    const res = await api.verifySlideCaptcha({
      captcha_id: submittedId,
      captcha_x: submittedX,
    })
    const ticket = res.data?.captcha_ticket
    if (submittedVersion !== challengeVersion || submittedId !== captchaId.value) return
    if (!ticket) throw new Error('滑块验证失败，请重试')
    verified.value = true
    emit('solved', { captcha_ticket: ticket })
  } catch (e) {
    if (submittedVersion !== challengeVersion || submittedId !== captchaId.value) return
    const reason = e?.error?.msg || e?.msg || e?.message || '滑块位置不正确，请重试'
    emit('cleared')
    await reload()
    errorMsg.value = reason
  } finally {
    if (submittedVersion === challengeVersion) verifying.value = false
  }
}

watch(
  () => props.resetKey,
  () => {
    reload()
  },
)

onMounted(reload)
onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onMove)
  window.removeEventListener('mouseup', onUp)
  window.removeEventListener('touchmove', onMove)
  window.removeEventListener('touchend', onUp)
})

defineExpose({ reload })
</script>

<style scoped>
.slide-captcha {
  user-select: none;
  margin-top: 16px;
}
.slide-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: #555;
}
.slide-title {
  font-weight: 600;
}
.slide-refresh {
  border: none;
  background: transparent;
  color: #2080f0;
  cursor: pointer;
  font-size: 13px;
  padding: 0 4px;
}
.slide-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.slide-err {
  color: #d03050;
  font-size: 12px;
  margin-bottom: 6px;
}
.slide-panel {
  position: relative;
  border-radius: 8px;
  overflow: hidden;
  background: #e8eef5;
  margin: 0 auto;
}
.slide-bg {
  width: 100%;
  height: 100%;
  display: block;
  pointer-events: none;
}
.slide-piece {
  position: absolute;
  left: 0;
  top: 0;
  pointer-events: none;
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.35));
}
.slide-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.55);
  font-size: 13px;
  color: #666;
}
.slide-track {
  position: relative;
  height: 40px;
  margin: 10px auto 0;
  background: #f0f2f5;
  border-radius: 20px;
  border: 1px solid #e0e0e0;
  overflow: hidden;
}
.slide-track-fill {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: rgba(32, 128, 240, 0.18);
  border-radius: 20px 0 0 20px;
  pointer-events: none;
}
.slide-btn {
  position: absolute;
  top: 2px;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: #fff;
  border: 1px solid #d0d5dd;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.12);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 16px;
  color: #2080f0;
  cursor: grab;
  z-index: 2;
}
.slide-btn.active {
  cursor: grabbing;
  border-color: #2080f0;
}
.slide-btn.ok {
  background: #18a058;
  color: #fff;
  border-color: #18a058;
}
.slide-hint {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #999;
  pointer-events: none;
  padding-left: 28px;
}
</style>
