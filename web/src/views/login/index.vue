<template>
  <div class="login-root">
    <!-- Layer 0–3：氛围（pointer-events:none；路由离开即卸载） -->
    <LoginAtmosphere />

    <!-- Layer 4–5：品牌 + 玻璃表单；登录/滑块/TOTP 语义不变 -->
    <div class="login-content">
      <div class="login-card">
        <div class="login-brand">
          <img
            class="login-brand-logo"
            :src="`${BASE_URL}resource/company-logo.jpg`"
            alt="系统标识"
            draggable="false"
          />
          <TypewriterTitle :text="titleText" />
        </div>

        <div class="login-field">
          <n-input
            v-model:value="loginInfo.username"
            autofocus
            class="h-50 items-center pl-10 text-16"
            placeholder="请输入用户名"
            :maxlength="20"
          />
        </div>
        <div class="login-field">
          <n-input
            v-model:value="loginInfo.password"
            class="h-50 items-center pl-10 text-16"
            type="password"
            show-password-on="mousedown"
            placeholder="请输入密码"
            :maxlength="20"
            @keypress.enter="handleLogin"
          />
        </div>

        <!-- 严格：每次登录必须滑块 -->
        <div class="login-field login-field--captcha">
          <SlideCaptcha
            :reset-key="captchaResetKey"
            @solved="onCaptchaSolved"
            @cleared="onCaptchaCleared"
          />
        </div>

        <!-- 零成本 TOTP：密码+滑块通过后才出现，不当失败 -->
        <div v-if="needTotp" class="login-field login-field--totp">
          <div class="totp-step-hint">密码已通过。请输入验证器中的 6 位动态码，并重新完成滑块。</div>
          <n-input
            v-model:value="totpCode"
            class="h-50 items-center pl-10 text-16"
            placeholder="验证器 6 位动态码"
            :maxlength="6"
            :allow-input="(value) => /^\d*$/.test(value)"
            inputmode="numeric"
            @keypress.enter="handleLogin"
          />
        </div>

        <template v-if="recoveryMode">
          <div class="login-field recovery-question">{{ recoveryQuestion }}</div>
          <div class="login-field">
            <n-input
              v-model:value="recoveryAnswer"
              class="h-50 items-center pl-10 text-16"
              type="password"
              show-password-on="mousedown"
              placeholder="请输入安全问题答案"
              :maxlength="128"
              @keypress.enter="handleLogin"
            />
          </div>
        </template>

        <div v-if="needTotp && recoveryQuestion && !recoveryMode" class="login-field recovery-action">
          <n-button text type="primary" @click="startRecovery">丢失验证器？使用安全问题恢复</n-button>
        </div>
        <div v-if="recoveryMode" class="login-field recovery-action">
          <n-button text @click="cancelRecovery">返回动态验证码登录</n-button>
        </div>

        <div class="login-field login-field--submit">
          <n-button
            h-50
            w-full
            rounded-5
            text-16
            type="primary"
            :loading="loading"
            @click="handleLogin"
          >
            {{ needTotp ? '验证并登录' : $t('views.login.text_login') }}
          </n-button>
        </div>

        <details v-if="needTotp" class="login-auth-dl">
          <summary>没有验证器？打开官方下载</summary>
          <AuthenticatorDownloadLinks compact />
        </details>
      </div>
    </div>
  </div>
</template>

<script setup>
import { lStorage, setToken, getHomePath, canWorkUserAccessPath, resolvePortal, isAdminLandingPath } from '@/utils'
import api from '@/api'
import { addDynamicRoutes } from '@/router'
import { useUserStore } from '@/store'
import { useI18n } from 'vue-i18n'
import SlideCaptcha from '@/components/login/SlideCaptcha.vue'
import AuthenticatorDownloadLinks from '@/components/security/AuthenticatorDownloadLinks.vue'
import LoginAtmosphere from './LoginAtmosphere.vue'
import TypewriterTitle from './TypewriterTitle.vue'
import './login-theme.css'

const BASE_URL = import.meta.env.BASE_URL || '/'

/** 打字机标题：配置常量，不进 v-html */
const titleText = '资产管理系统'

const router = useRouter()
const { query } = useRoute()
const { t } = useI18n({ useScope: 'global' })

const loginInfo = ref({
  username: '',
  password: '',
})

const captchaResetKey = ref(0)
const captchaPayload = ref(null)
const needTotp = ref(false)
const totpCode = ref('')
const recoveryMode = ref(false)
const recoveryQuestion = ref('')
const recoveryAnswer = ref('')

initLoginInfo()

function initLoginInfo() {
  const localLoginInfo = lStorage.get('loginInfo')
  if (localLoginInfo) {
    loginInfo.value.username = localLoginInfo.username || ''
    loginInfo.value.password = ''
  }
}

function onCaptchaSolved(payload) {
  captchaPayload.value = payload
}

function onCaptchaCleared() {
  captchaPayload.value = null
}

function refreshCaptcha() {
  captchaPayload.value = null
  captchaResetKey.value += 1
}

function startRecovery() {
  recoveryMode.value = true
  needTotp.value = false
  totpCode.value = ''
  refreshCaptcha()
  $message.info('恢复操作必须重新完成滑块验证')
}

function cancelRecovery() {
  recoveryMode.value = false
  needTotp.value = true
  recoveryAnswer.value = ''
  refreshCaptcha()
}

function collectDeviceProfile() {
  if (typeof window === 'undefined') {
    return { device_hint: '' }
  }
  const device_hint = `${window.screen?.width || 0}x${window.screen?.height || 0}`
  let timezone = ''
  try {
    timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || ''
  } catch (e) {
    timezone = ''
  }
  const uaData = navigator.userAgentData
  const platform = String(uaData?.platform || navigator.platform || '').slice(0, 64)
  const languages = String(
    navigator.languages && navigator.languages.length
      ? navigator.languages.join(',')
      : navigator.language || ''
  ).slice(0, 128)
  return { device_hint, timezone, platform, languages }
}

const loading = ref(false)
async function handleLogin() {
  const { username, password } = loginInfo.value
  if (!username || !password) {
    $message.warning(t('views.login.message_input_username_password'))
    return
  }
  if (!captchaPayload.value?.captcha_ticket) {
    $message.warning('请先完成滑块验证')
    return
  }
  try {
    loading.value = true
    $message.loading(t('views.login.message_verifying'))
    if (recoveryMode.value) {
      if (!recoveryAnswer.value) {
        $message.warning('请输入安全问题答案')
        return
      }
      const res = await api.recoverTotp({
        username,
        password: password.toString(),
        answer: recoveryAnswer.value,
        captcha_ticket: captchaPayload.value.captcha_ticket,
        ...collectDeviceProfile(),
      })
      setToken(res.data.access_token)
      $message.success('恢复验证通过，请重新绑定动态验证器')
      router.replace({ path: '/profile', query: { totpRecovery: '1' } })
      return
    }
    const res = await api.login({
      username,
      password: password.toString(),
      captcha_ticket: captchaPayload.value.captcha_ticket,
      totp_code: needTotp.value ? totpCode.value : undefined,
      ...collectDeviceProfile(),
    })
    $message.success(t('views.login.message_login_success'))
    captchaPayload.value = null
    needTotp.value = false
    totpCode.value = ''
    setToken(res.data.access_token)
    const userStore = useUserStore()
    userStore.setUserInfo({
      security_setup_only: !!res.data.security_setup_only,
      totp_recovery_only: !!res.data.totp_recovery_only,
      must_change_password: !!res.data.must_change_password,
    })
    if (res.data.security_setup_only || res.data.totp_recovery_only) {
      router.replace({
        path: '/profile',
        query: res.data.totp_recovery_only
          ? { totpRecovery: '1' }
          : {
              securitySetup: '1',
              forceChangePassword: res.data.must_change_password ? '1' : undefined,
            },
      })
      return
    }
    if (res.data.must_change_password) {
      router.push({ path: '/profile', query: { forceChangePassword: '1' } })
      return
    }
    await addDynamicRoutes()
    const portal = resolvePortal(userStore.userInfo)
    const home = getHomePath(portal)
    if (query.redirect) {
      const path = query.redirect
      Reflect.deleteProperty(query, 'redirect')
      // work 用户：不可进的路径，以及指向 /workbench 或 / 的 redirect，一律回工作台
      if (portal === 'work' && (!canWorkUserAccessPath(path) || isAdminLandingPath(path))) {
        router.push(home)
      } else {
        router.push({ path, query })
      }
    } else {
      router.push(home)
    }
  } catch (e) {
    console.error('login error', e)
    // 需要 TOTP 时展示输入框（密码已通过，但 captcha 已消费，须重滑）
    const data = e?.error?.data || e?.error || {}
    const payload = data.data && typeof data.data === 'object' ? data.data : data
    if (payload.require_totp || data.require_totp) {
      needTotp.value = true
      recoveryMode.value = false
      recoveryQuestion.value = payload.recovery_question || data.recovery_question || ''
      if (payload.totp_challenge || data.totp_challenge) {
        $message?.info?.('密码已通过，请输入验证器 6 位动态码')
      }
    }
    refreshCaptcha()
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 全局 login-theme.css 负责布局；此处再钉一层 Naive 计算样式（scoped+deep 必生效） */
.login-card :deep(.n-input .n-input-wrapper) {
  background-color: rgba(8, 15, 28, 0.78) !important;
  background-image: none !important;
  border-radius: 10px !important;
  box-shadow: inset 0 0 0 1px rgba(125, 211, 252, 0.28) !important;
}
.login-card :deep(.n-input .n-input__input-el) {
  color: #e2e8f0 !important;
  -webkit-text-fill-color: #e2e8f0 !important;
  caret-color: #38bdf8 !important;
}
.login-card :deep(.n-input .n-input__placeholder),
.login-card :deep(.n-input .n-input__placeholder *) {
  color: rgba(226, 232, 240, 0.42) !important;
}
.login-card :deep(.n-input .n-base-icon) {
  color: rgba(186, 230, 253, 0.8) !important;
}
.login-card :deep(.n-button.n-button--primary-type) {
  background-color: #0ea5e9 !important;
  color: #041018 !important;
  border: none !important;
  font-weight: 600 !important;
  height: 50px !important;
  border-radius: 10px !important;
}
.login-card :deep(.n-button.n-button--primary-type .n-button__content) {
  color: #041018 !important;
}
.login-card :deep(.slide-captcha .slide-head) {
  color: rgba(226, 232, 240, 0.72);
}
.login-card :deep(.slide-captcha .slide-refresh) {
  color: #38bdf8;
}
.login-card :deep(.slide-captcha .slide-track) {
  background: rgba(8, 15, 28, 0.55);
  border-color: rgba(125, 211, 252, 0.25);
}
.login-card :deep(.slide-captcha .slide-hint) {
  color: rgba(226, 232, 240, 0.45);
}
.login-card :deep(.slide-captcha .slide-err) {
  color: #f87171;
}
.login-card :deep(.slide-captcha .slide-panel) {
  background: rgba(8, 15, 28, 0.55);
  border: 1px solid rgba(125, 211, 252, 0.2);
}
.login-card :deep(.slide-captcha .slide-loading) {
  background: rgba(5, 11, 22, 0.72);
  color: rgba(226, 232, 240, 0.72);
}
.login-card :deep(.slide-captcha .slide-btn) {
  background: rgba(15, 23, 42, 0.95);
  border-color: rgba(125, 211, 252, 0.45);
  color: #38bdf8;
}
.login-card :deep(.slide-captcha .slide-btn.ok) {
  background: #059669;
  border-color: #34d399;
  color: #ecfdf5;
}
.login-card :deep(.n-input .n-input__input-el:-webkit-autofill) {
  -webkit-text-fill-color: #e2e8f0 !important;
  box-shadow: 0 0 0 1000px rgba(8, 15, 28, 0.92) inset !important;
}
.totp-step-hint {
  color: rgba(186, 230, 253, 0.92);
  font-size: 13px;
  line-height: 1.5;
  margin-bottom: 8px;
}
.recovery-question {
  color: rgba(226, 232, 240, 0.86);
  font-size: 14px;
  line-height: 1.6;
}
.recovery-action {
  text-align: right;
}
</style>
