<template>
  <div v-if="active" class="acceptance-banner" role="status">
    限时验收模式已开启：登录暂不要求动态码，高危操作策略未改。剩余 {{ remainText }}，到期自动恢复。
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useUserStore } from '@/store'

const userStore = useUserStore()
const nowTick = ref(Date.now())
let timer = null

onMounted(() => {
  timer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

const expiresAt = computed(() => {
  const raw = userStore.userInfo?.acceptance_mode?.expires_at
  return raw ? Date.parse(raw) : NaN
})

const active = computed(() => {
  nowTick.value
  const flagged = !!userStore.userInfo?.acceptance_mode?.active
  return flagged && Number.isFinite(expiresAt.value) && expiresAt.value > Date.now()
})

const remainText = computed(() => {
  nowTick.value
  const ms = expiresAt.value - Date.now()
  if (!Number.isFinite(ms) || ms <= 0) return '不足 1 分钟'
  const total = Math.floor(ms / 1000)
  const hours = Math.floor(total / 3600)
  const minutes = Math.floor((total % 3600) / 60)
  if (hours > 0) return `${hours} 小时 ${minutes} 分`
  if (minutes > 0) return `${minutes} 分`
  return '不足 1 分钟'
})
</script>

<style scoped>
.acceptance-banner {
  flex: 0 0 auto;
  padding: 8px 16px;
  color: #7a3d00;
  font-size: 13px;
  line-height: 1.5;
  text-align: center;
  background: #fff4d6;
  border-bottom: 1px solid #f0c36d;
}
</style>
