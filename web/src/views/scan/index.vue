<template>
  <div class="scan-page">
    <header class="scan-page__head">
      <img
        :src="`${BASE_URL}resource/company-logo.jpg`"
        alt=""
        width="40"
        height="40"
        draggable="false"
      />
      <div>
        <p>手机扫码</p>
        <h1>资产详情</h1>
      </div>
    </header>
    <p v-if="loading" class="scan-page__state">正在查找资产…</p>
    <p v-else-if="errorText" class="scan-page__state">{{ errorText }}</p>
    <article v-else-if="asset" class="scan-card">
      <div class="scan-card__identity">
        <div>
          <p class="scan-card__label">资产编号</p>
          <p class="scan-card__no">{{ asset.asset_no }}</p>
        </div>
        <NTag :type="statusType[asset.status] || 'default'" round>
          {{ statusMap[asset.status] || '状态异常' }}
        </NTag>
      </div>
      <p class="scan-card__label">资产名称</p>
      <h2>{{ asset.name || '-' }}</h2>
      <NAlert v-if="statusNotice" class="scan-card__notice" type="warning" :show-icon="false">
        {{ statusNotice }}
      </NAlert>
      <dl>
        <div>
          <dt>状态</dt>
          <dd>{{ statusMap[asset.status] || '-' }}</dd>
        </div>
        <div>
          <dt>分类</dt>
          <dd>{{ asset.category || '-' }}</dd>
        </div>
        <div>
          <dt>型号</dt>
          <dd>{{ asset.model || '-' }}</dd>
        </div>
        <div>
          <dt>位置</dt>
          <dd>{{ asset.location || '-' }}</dd>
        </div>
        <div v-if="asset.warranty_label">
          <dt>质保</dt>
          <dd>{{ asset.warranty_label }}</dd>
        </div>
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
import { NAlert, NButton, NTag } from 'naive-ui'
import { usePermissionStore, useUserStore } from '@/store'
import api from '@/api'
import { getHomePath } from '@/utils'
import { assetActionLocation, canUseScanAction, scanAssetStatusNotice } from '@/utils/asset-qr'

defineOptions({ name: 'AssetScan' })

const BASE_URL = import.meta.env.BASE_URL || '/'
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const permissionStore = usePermissionStore()
const loading = ref(true)
const errorText = ref('')
const asset = ref(null)
const ownAssetIds = ref([])
const hasActiveEmployee = ref(false)
let loadRequestId = 0
const statusMap = { 1: '在用', 2: '闲置', 3: '维修', 4: '报废' }
const statusType = { 1: 'success', 2: 'info', 3: 'warning', 4: 'error' }

const actionContext = computed(() => ({
  accessApis: permissionStore.accessApis || [],
  portal: userStore.portal,
  ownAssetIds: ownAssetIds.value,
  hasActiveEmployee: hasActiveEmployee.value,
}))
const canRepair = computed(() => canUseScanAction('repair', asset.value, actionContext.value))
const canTransfer = computed(() => canUseScanAction('transfer', asset.value, actionContext.value))
const statusNotice = computed(() => scanAssetStatusNotice(asset.value?.status))

function goHome() {
  router.push(getHomePath(userStore.portal))
}

function goRepair() {
  const location = assetActionLocation('repair', asset.value, userStore.portal)
  if (location) router.push(location)
}

function goTransfer() {
  const location = assetActionLocation('transfer', asset.value, userStore.portal)
  if (location) router.push(location)
}

async function load() {
  const requestId = ++loadRequestId
  const assetNo = String(route.params.assetNo || '').trim()
  loading.value = true
  errorText.value = ''
  asset.value = null
  ownAssetIds.value = []
  hasActiveEmployee.value = false
  if (!assetNo) {
    errorText.value = '这个二维码里没有有效的资产编号，请重新扫码。'
    loading.value = false
    return
  }
  try {
    const [assetRes, contextRes] = await Promise.all([
      api.getAssetByNo({ asset_no: assetNo }),
      api.getAssetActionContext(),
    ])
    if (requestId !== loadRequestId) return
    asset.value = assetRes.data || null
    ownAssetIds.value = contextRes.data?.own_asset_ids || []
    hasActiveEmployee.value = contextRes.data?.has_active_employee === true
  } catch (error) {
    if (requestId !== loadRequestId) return
    errorText.value = [403, 404].includes(Number(error?.code))
      ? '没有找到这台资产，也可能是当前账号没有查看权限。请核对资产编号或联系管理员。'
      : '资产信息暂时没有查到，请稍后重试。'
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

onMounted(load)
watch(() => route.params.assetNo, load)
</script>

<style scoped>
.scan-page {
  box-sizing: border-box;
  min-height: 100vh;
  padding: 20px 16px 32px;
  max-width: 480px;
  margin: 0 auto;
  color: #172033;
  background: linear-gradient(180deg, #f4f8fc 0%, #eef3f8 100%);
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
  padding: 18px;
  border-radius: 12px;
  background: #fff;
  line-height: 1.6;
}
.scan-card {
  padding: 16px;
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
}
.scan-card__identity {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}
.scan-card__label {
  margin: 0;
  color: #667085;
  font-size: 12px;
}
.scan-card__no {
  margin: 2px 0 14px;
  color: #1d4ed8;
  font-size: 18px;
  font-weight: 700;
  overflow-wrap: anywhere;
}
.scan-card__identity .scan-card__no {
  margin-bottom: 0;
}
.scan-card__notice {
  margin-bottom: 14px;
  line-height: 1.6;
}
.scan-card__identity :deep(.n-tag) {
  flex: 0 0 auto;
}
.scan-card__identity + .scan-card__label {
  margin-top: 16px;
}
.scan-card__label,
.scan-card dt {
  opacity: 0.65;
}
.scan-card h2 {
  margin: 3px 0 14px;
  font-size: 22px;
  line-height: 1.35;
  overflow-wrap: anywhere;
}
.scan-card dl {
  display: grid;
  gap: 8px;
  margin: 0 0 16px;
}
.scan-card dl div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
}
.scan-card dd {
  margin: 0;
  text-align: right;
  overflow-wrap: anywhere;
}
.scan-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
@media (max-width: 420px) {
  .scan-page {
    padding: 12px 10px 24px;
  }
  .scan-card {
    padding: 14px;
  }
  .scan-card h2 {
    font-size: 20px;
  }
  .scan-card__actions {
    display: grid;
    grid-template-columns: 1fr;
  }
  .scan-card__actions :deep(.n-button) {
    width: 100%;
  }
}
</style>
