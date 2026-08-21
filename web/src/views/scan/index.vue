<template>
  <div class="scan-page">
    <header class="scan-page__head">
      <img :src="`${BASE_URL}resource/company-logo.jpg`" alt="" width="40" height="40" draggable="false" />
      <div>
        <p>手机扫码</p>
        <h1>资产详情</h1>
      </div>
    </header>
    <p v-if="loading" class="scan-page__state">正在查找资产…</p>
    <p v-else-if="errorText" class="scan-page__state">{{ errorText }}</p>
    <article v-else-if="asset" class="scan-card">
      <p class="scan-card__no">{{ asset.asset_no }}</p>
      <h2>{{ asset.name }}</h2>
      <dl>
        <div><dt>状态</dt><dd>{{ statusMap[asset.status] || '-' }}</dd></div>
        <div><dt>分类</dt><dd>{{ asset.category || '-' }}</dd></div>
        <div><dt>位置</dt><dd>{{ asset.location || '-' }}</dd></div>
        <div v-if="asset.warranty_label"><dt>质保</dt><dd>{{ asset.warranty_label }}</dd></div>
      </dl>
      <div class="scan-card__actions">
        <NButton v-if="canRepair" type="warning" @click="goRepair">报修</NButton>
        <NButton v-if="canTransfer" type="primary" @click="goTransfer">调拨</NButton>
        <NButton quaternary @click="goHome">返回</NButton>
      </div>
    </article>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton } from 'naive-ui'
import { usePermissionStore, useUserStore } from '@/store'
import api from '@/api'
import { getHomePath } from '@/utils'

defineOptions({ name: 'AssetScan' })

const BASE_URL = import.meta.env.BASE_URL || '/'
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const loading = ref(true)
const errorText = ref('')
const asset = ref(null)
const statusMap = { 1: '在用', 2: '闲置', 3: '维修', 4: '报废' }

function hasApi(path) {
  return (permissionStore.accessApis || []).includes(path)
}

const canRepair = computed(
  () => asset.value?.status === 1 && hasApi('post/api/v1/asset-repair/apply')
)
const canTransfer = computed(
  () => asset.value?.status === 1 && hasApi('post/api/v1/asset-transfer/apply')
)

function goHome() {
  router.push(getHomePath(userStore.portal))
}

function goRepair() {
  router.push({ path: userStore.portal === 'admin' ? '/business/repair' : '/work/repair' })
}

function goTransfer() {
  router.push({ path: userStore.portal === 'admin' ? '/business/transfer' : '/work/transfer' })
}

async function load() {
  const assetNo = decodeURIComponent(String(route.params.assetNo || '')).trim()
  loading.value = true
  errorText.value = ''
  asset.value = null
  if (!assetNo) {
    errorText.value = '二维码无效'
    loading.value = false
    return
  }
  try {
    const res = await api.getAssetList({ keyword: assetNo, page: 1, page_size: 20 })
    const list = res.data?.list || []
    const hit = list.find((row) => row.asset_no === assetNo)
    if (!hit) {
      errorText.value = '找不到这台资产，或你无权查看。闲置资产需登录后才显示摘要。'
      return
    }
    asset.value = hit
  } catch (err) {
    errorText.value = err?.msg || err?.message || '查询失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
watch(() => route.params.assetNo, load)
</script>

<style scoped>
.scan-page {
  min-height: 100vh;
  padding: 20px 16px 32px;
  max-width: 480px;
  margin: 0 auto;
}
.scan-page__head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}
.scan-page__head img {
  border-radius: 50%;
}
.scan-page__head p {
  margin: 0;
  font-size: 12px;
  opacity: 0.7;
}
.scan-page__head h1 {
  margin: 0;
  font-size: 20px;
}
.scan-page__state {
  line-height: 1.6;
}
.scan-card {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}
.scan-card__no {
  margin: 0;
  font-size: 13px;
  opacity: 0.65;
}
.scan-card h2 {
  margin: 4px 0 12px;
  font-size: 22px;
}
.scan-card dl {
  display: grid;
  gap: 8px;
  margin: 0 0 16px;
}
.scan-card dl div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}
.scan-card dt {
  opacity: 0.65;
}
.scan-card dd {
  margin: 0;
  text-align: right;
}
.scan-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
