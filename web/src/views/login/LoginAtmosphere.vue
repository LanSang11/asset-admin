<template>
  <!-- 纯展示氛围层：失败/降级时不影响登录；强制 pointer-events:none -->
  <div
    ref="layerRef"
    class="login-atmosphere"
    :class="{
      'is-reduced': reducedMotion,
      'is-static-spot': !followEnabled,
    }"
    aria-hidden="true"
  >
    <!-- Layer 0：深海底色渐变 -->
    <div class="atm-base" />

    <!-- Layer 1：缓慢呼吸光斑（纯 CSS，无 JS） -->
    <div class="atm-breathe atm-breathe--a" />
    <div class="atm-breathe atm-breathe--b" />
    <div class="atm-breathe atm-breathe--c" />

    <!-- Layer 2：鼠标跟随径向光（CSS 变量 --mx --my） -->
    <div class="atm-spotlight" />

    <!-- Layer 3：极轻 CSS 气泡粒子（桌面默认开；移动/降级关） -->
    <div v-if="particlesOn" class="atm-particles">
      <span v-for="i in particleCount" :key="i" class="atm-dot" :style="dotStyle(i)" />
    </div>

    <!-- 底部青蓝晕 -->
    <div class="atm-horizon" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'

const props = defineProps({
  /** 是否启用极轻粒子（桌面默认 true；降级时强制关） */
  particles: { type: Boolean, default: true },
  /** 粒子数量上限（≤40） */
  particleCount: { type: Number, default: 28 },
})

const layerRef = ref(null)
const reducedMotion = ref(false)
const followEnabled = ref(true)
const particlesOn = ref(false)

/** 目标 / 当前光斑位置（百分比）；不进 Vue 响应式，避免每帧重渲染 */
let targetX = 50
let targetY = 42
let curX = 50
let curY = 42
let rafId = 0
let hostEl = null

const LERP = 0.16

function setCssVars(x, y, alpha) {
  if (!hostEl) return
  hostEl.style.setProperty('--mx', `${x.toFixed(2)}%`)
  hostEl.style.setProperty('--my', `${y.toFixed(2)}%`)
  if (typeof alpha === 'number') {
    hostEl.style.setProperty('--spotlight-alpha', String(alpha))
  }
}

function tick() {
  rafId = 0
  if (!followEnabled.value || reducedMotion.value) return

  curX += (targetX - curX) * LERP
  curY += (targetY - curY) * LERP
  setCssVars(curX, curY)

  if (Math.abs(targetX - curX) > 0.04 || Math.abs(targetY - curY) > 0.04) {
    rafId = requestAnimationFrame(tick)
  }
}

function scheduleTick() {
  if (!rafId) {
    rafId = requestAnimationFrame(tick)
  }
}

function updateTargetFromEvent(e) {
  if (!hostEl || !followEnabled.value || reducedMotion.value) return
  const rect = hostEl.getBoundingClientRect()
  if (!rect.width || !rect.height) return
  const x = ((e.clientX - rect.left) / rect.width) * 100
  const y = ((e.clientY - rect.top) / rect.height) * 100
  targetX = Math.min(100, Math.max(0, x))
  targetY = Math.min(100, Math.max(0, y))
  setCssVars(curX, curY, 0.18)
  scheduleTick()
}

function onPointerMove(e) {
  // 仅指针类设备跟随时处理；触控在 touch 路径
  if (e.pointerType === 'touch') return
  updateTargetFromEvent(e)
}

function onTouchMove(e) {
  // 移动端轻量跟随：取第一触点；不 preventDefault，避免挡滚动/滑块
  const t = e.touches && e.touches[0]
  if (!t || !followEnabled.value || reducedMotion.value) return
  updateTargetFromEvent(t)
}

function onPointerLeave() {
  if (reducedMotion.value) return
  // 缓回中心并略降透明度
  targetX = 50
  targetY = 42
  setCssVars(curX, curY, 0.1)
  scheduleTick()
}

function resolveHost() {
  // 优先写到 .login-root，便于 token 与 spotlight 共用变量
  const el = layerRef.value
  if (!el) return null
  return el.closest('.login-root') || el
}

function detectCaps() {
  const mqReduce =
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(prefers-reduced-motion: reduce)')
      : null
  reducedMotion.value = !!(mqReduce && mqReduce.matches)

  // 粗粒度：窄屏 / 无 hover 视为移动端，关闭粒子、可选弱跟随
  const mqNarrow =
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(max-width: 768px)')
      : null
  const mqHover =
    typeof window !== 'undefined' && window.matchMedia
      ? window.matchMedia('(hover: hover) and (pointer: fine)')
      : null

  const isMobileLike = !!(mqNarrow && mqNarrow.matches) || !(mqHover && mqHover.matches)

  if (reducedMotion.value) {
    followEnabled.value = false
    particlesOn.value = false
    setCssVars(50, 40, 0.08)
    return
  }

  followEnabled.value = true
  // 粒子：默认仅桌面且 props 允许
  particlesOn.value = !!props.particles && !isMobileLike
}

function onReduceChange(e) {
  reducedMotion.value = !!e.matches
  detectCaps()
  if (reducedMotion.value && rafId) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
}

/** 确定性伪随机样式，避免 SSR/hydration 抖动 */
function dotStyle(i) {
  const n = ((i * 47) % 97) / 97
  const n2 = ((i * 31) % 89) / 89
  const left = (n * 100).toFixed(2)
  const top = (n2 * 100).toFixed(2)
  const size = 2 + ((i * 13) % 4)
  const dur = 12 + ((i * 7) % 18)
  const delay = -((i * 3) % 20)
  const opacity = 0.15 + n * 0.35
  return {
    left: `${left}%`,
    top: `${top}%`,
    width: `${size}px`,
    height: `${size}px`,
    opacity: String(opacity),
    animationDuration: `${dur}s`,
    animationDelay: `${delay}s`,
  }
}

let mqReduceRef = null

onMounted(() => {
  hostEl = resolveHost()
  detectCaps()

  if (typeof window === 'undefined' || !hostEl) return

  mqReduceRef =
    window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)')
  if (mqReduceRef) {
    if (mqReduceRef.addEventListener) {
      mqReduceRef.addEventListener('change', onReduceChange)
    } else if (mqReduceRef.addListener) {
      mqReduceRef.addListener(onReduceChange)
    }
  }

  // 在 login-root 上监听，氛围层自身 pointer-events:none
  hostEl.addEventListener('pointermove', onPointerMove, { passive: true })
  hostEl.addEventListener('pointerleave', onPointerLeave, { passive: true })
  hostEl.addEventListener('touchmove', onTouchMove, { passive: true })
})

onBeforeUnmount(() => {
  if (rafId) {
    cancelAnimationFrame(rafId)
    rafId = 0
  }
  if (hostEl) {
    hostEl.removeEventListener('pointermove', onPointerMove)
    hostEl.removeEventListener('pointerleave', onPointerLeave)
    hostEl.removeEventListener('touchmove', onTouchMove)
  }
  if (mqReduceRef) {
    if (mqReduceRef.removeEventListener) {
      mqReduceRef.removeEventListener('change', onReduceChange)
    } else if (mqReduceRef.removeListener) {
      mqReduceRef.removeListener(onReduceChange)
    }
  }
  hostEl = null
  // 路由离开即卸载，业务页零执行
})
</script>

<style scoped>
.login-atmosphere {
  position: absolute;
  inset: 0;
  z-index: 0;
  overflow: hidden;
  pointer-events: none !important;
  contain: strict;
}

.atm-base {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(120% 80% at 50% 100%, rgba(14, 116, 144, 0.22) 0%, transparent 55%),
    radial-gradient(90% 60% at 20% 10%, rgba(30, 64, 175, 0.35) 0%, transparent 50%),
    linear-gradient(165deg, #050b16 0%, #0a1628 48%, #07101f 100%);
}

.atm-breathe {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.55;
  will-change: transform, opacity;
  animation: yd-breathe 14s ease-in-out infinite;
}

.atm-breathe--a {
  width: min(52vw, 420px);
  height: min(52vw, 420px);
  left: -8%;
  top: 12%;
  background: rgba(56, 189, 248, 0.22);
}

.atm-breathe--b {
  width: min(48vw, 380px);
  height: min(48vw, 380px);
  right: -6%;
  top: 38%;
  background: rgba(34, 211, 238, 0.14);
  animation-duration: 18s;
  animation-delay: -4s;
}

.atm-breathe--c {
  width: min(60vw, 480px);
  height: min(40vw, 320px);
  left: 28%;
  bottom: -10%;
  background: rgba(37, 99, 235, 0.18);
  animation-duration: 20s;
  animation-delay: -8s;
}

.atm-spotlight {
  position: absolute;
  inset: 0;
  background: radial-gradient(
    600px circle at var(--mx, 50%) var(--my, 42%),
    rgba(56, 189, 248, var(--spotlight-alpha, 0.18)),
    transparent 55%
  );
  transition: opacity 0.35s ease;
}

.atm-horizon {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 28%;
  background: linear-gradient(
    to top,
    rgba(8, 47, 73, 0.45) 0%,
    transparent 100%
  );
  opacity: 0.7;
}

.atm-particles {
  position: absolute;
  inset: 0;
}

.atm-dot {
  position: absolute;
  border-radius: 50%;
  background: rgba(186, 230, 253, 0.85);
  box-shadow: 0 0 6px rgba(56, 189, 248, 0.45);
  animation-name: yd-float;
  animation-timing-function: ease-in-out;
  animation-iteration-count: infinite;
  will-change: transform, opacity;
}

.is-reduced .atm-breathe,
.is-reduced .atm-dot {
  animation: none !important;
}

.is-reduced .atm-breathe {
  opacity: 0.28;
}

.is-static-spot .atm-spotlight {
  /* 跟随关闭时保持居中极淡 */
  opacity: 0.85;
}

@keyframes yd-breathe {
  0%,
  100% {
    transform: translate3d(0, 0, 0) scale(1);
    opacity: 0.45;
  }
  50% {
    transform: translate3d(12px, -18px, 0) scale(1.08);
    opacity: 0.7;
  }
}

@keyframes yd-float {
  0%,
  100% {
    transform: translate3d(0, 0, 0);
  }
  50% {
    transform: translate3d(0, -18px, 0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .atm-breathe,
  .atm-dot {
    animation: none !important;
  }
}
</style>
