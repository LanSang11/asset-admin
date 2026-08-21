<template>
  <NModal :show="show" preset="card" title="资产二维码（给手机扫）" style="width: 420px" @update:show="onShow">
    <div class="asset-qr">
      <p class="asset-qr__hint">用手机相机或微信扫一扫。打开后登录，按你的权限查看这台资产。</p>
      <div v-if="qrDataUrl" class="asset-qr__frame">
        <img :src="qrDataUrl" alt="资产二维码" width="240" height="240" draggable="false" />
      </div>
      <p v-else class="asset-qr__wait">正在生成二维码…</p>
      <p class="asset-qr__meta">
        <strong>{{ asset?.asset_no || '-' }}</strong>
        <span>{{ asset?.name || '' }}</span>
      </p>
      <p class="asset-qr__url">{{ scanUrl }}</p>
    </div>
    <template #footer>
      <NButton @click="onShow(false)">关闭</NButton>
      <NButton type="primary" :disabled="!scanUrl" @click="copyUrl">复制链接</NButton>
    </template>
  </NModal>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { NButton, NModal } from 'naive-ui'
import { assetScanUrl } from '@/utils/asset-qr'

const props = defineProps({
  show: { type: Boolean, default: false },
  asset: { type: Object, default: null },
})
const emit = defineEmits(['update:show'])

const qrDataUrl = ref('')
const scanUrl = computed(() => assetScanUrl(props.asset?.asset_no || ''))

watch(
  () => [props.show, props.asset?.asset_no],
  async () => {
    qrDataUrl.value = ''
    if (!props.show || !scanUrl.value) return
    const QRCode = (await import('qrcode')).default
    qrDataUrl.value = await QRCode.toDataURL(scanUrl.value, {
      width: 240,
      margin: 2,
      errorCorrectionLevel: 'M',
    })
  },
)

function onShow(value) {
  emit('update:show', value)
}

async function copyUrl() {
  if (!scanUrl.value) return
  try {
    await navigator.clipboard.writeText(scanUrl.value)
    window.$message?.success?.('已复制，发给手机浏览器也能打开')
  } catch (_) {
    window.$message?.info?.(scanUrl.value)
  }
}
</script>

<style scoped>
.asset-qr {
  text-align: center;
}
.asset-qr__hint {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  text-align: left;
}
.asset-qr__frame {
  display: inline-block;
  padding: 12px;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
}
.asset-qr__frame img {
  display: block;
}
.asset-qr__wait,
.asset-qr__meta,
.asset-qr__url {
  margin: 10px 0 0;
  word-break: break-all;
}
.asset-qr__meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.asset-qr__url {
  font-size: 12px;
  opacity: 0.75;
}
</style>
