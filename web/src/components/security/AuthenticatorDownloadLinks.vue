<template>
  <div class="auth-dl" :class="{ 'auth-dl--compact': compact }">
    <p class="auth-dl__title">用手机打开官方商店下载验证器（不要下不明 APK）：</p>
    <ul class="auth-dl__list">
      <li v-for="item in downloads" :key="item.id">
        <a :href="item.href" target="_blank" rel="noopener noreferrer">{{ item.label }}（{{ item.store }}）</a>
      </li>
    </ul>
    <p class="auth-dl__hint">
      中国区 App Store 通常没有 Google Authenticator，苹果请用上面的 Microsoft Authenticator。国内安卓若打不开
      Google Play，在应用商店搜索「身份验证器」或「Microsoft Authenticator」。
    </p>
  </div>
</template>

<script setup>
import { GOOGLE_AUTHENTICATOR_DOWNLOADS } from '@/constants/authenticator-apps'

defineProps({
  compact: { type: Boolean, default: false },
})

const downloads = GOOGLE_AUTHENTICATOR_DOWNLOADS
</script>

<style scoped>
.auth-dl {
  margin: 8px 0 12px;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.04);
}
.auth-dl--compact {
  padding: 8px 10px;
  background: rgba(8, 15, 28, 0.35);
}
.auth-dl__title {
  margin: 0 0 6px;
  font-size: 13px;
  line-height: 1.5;
}
.auth-dl__list {
  margin: 0;
  padding-left: 18px;
  line-height: 1.7;
}
.auth-dl__list a {
  color: var(--primary-color, #0ea5e9);
  text-decoration: underline;
}
.auth-dl__hint {
  margin: 6px 0 0;
  font-size: 12px;
  line-height: 1.5;
  opacity: 0.78;
}
</style>
