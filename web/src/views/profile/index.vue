<script setup>
import { computed, onMounted, ref } from 'vue'
import { NButton, NForm, NFormItem, NInput, NTabPane, NTabs, NImage, NAlert } from 'naive-ui'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import CommonPage from '@/components/page/CommonPage.vue'
import AuthenticatorDownloadLinks from '@/components/security/AuthenticatorDownloadLinks.vue'
import { useUserStore } from '@/store'
import api from '@/api'
import { is, removeToken } from '@/utils'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const isLoading = ref(false)
// 强制改密模式：首次登录或管理员重置密码后，必须修改密码才能进入系统
const isForceChange = computed(() => route.query.forceChangePassword === '1')
const isSecuritySetup = computed(() => route.query.securitySetup === '1')
const isTotpRecovery = computed(() => route.query.totpRecovery === '1')
const isRestrictedSecurity = computed(() => isSecuritySetup.value || isTotpRecovery.value)
const profileTab = ref(
  isTotpRecovery.value || isSecuritySetup.value ? 'totp' : isForceChange.value ? 'contact' : 'totp'
)

// 用户信息的表单
const infoFormRef = ref(null)
const infoForm = ref({
  avatar: userStore.avatar,
  username: userStore.name,
  email: userStore.email,
})
async function updateProfile() {
  isLoading.value = true
  infoFormRef.value?.validate(async (err) => {
    if (err) return
    await api
      .updateUser({ ...infoForm.value, id: userStore.userId })
      .then(() => {
        userStore.setUserInfo(infoForm.value)
        isLoading.value = false
        $message.success(t('common.text.update_success'))
      })
      .catch(() => {
        isLoading.value = false
      })
  })
}
const infoFormRules = {
  username: [
    {
      required: true,
      message: t('views.profile.message_username_required'),
      trigger: ['input', 'blur', 'change'],
    },
  ],
}

// 修改密码的表单
const passwordFormRef = ref(null)
const passwordForm = ref({
  old_password: '',
  new_password: '',
  confirm_password: '',
})

async function updatePassword() {
  isLoading.value = true
  passwordFormRef.value?.validate(async (err) => {
    if (!err) {
      const data = { ...passwordForm.value, id: userStore.userId }
      await api
        .updatePassword(data)
        .then(async (res) => {
          $message.success(res.msg)
          passwordForm.value = {
            old_password: '',
            new_password: '',
            confirm_password: '',
          }
          isLoading.value = false
          // 改密会递增认证版本，使当前令牌立即失效。
          if (isForceChange.value && isRestrictedSecurity.value) {
            removeToken()
            $message.info('密码已更新，请重新登录后继续完成动态验证器设置')
            router.replace('/login')
            return
          }
          if (isForceChange.value) {
            removeToken()
            $message.info('密码已更新，请重新登录')
            router.replace('/login')
          }
        })
        .catch(() => {
          isLoading.value = false
        })
    }
  })
}
const passwordFormRules = {
  old_password: [
    {
      required: true,
      message: t('views.profile.message_old_password_required'),
      trigger: ['input', 'blur', 'change'],
    },
  ],
  new_password: [
    {
      required: true,
      message: t('views.profile.message_new_password_required'),
      trigger: ['input', 'blur', 'change'],
    },
  ],
  confirm_password: [
    {
      required: true,
      message: t('views.profile.message_password_confirmation_required'),
      trigger: ['input', 'blur'],
    },
    {
      validator: validatePasswordStartWith,
      message: t('views.profile.message_password_confirmation_diff'),
      trigger: 'input',
    },
    {
      validator: validatePasswordSame,
      message: t('views.profile.message_password_confirmation_diff'),
      trigger: ['blur', 'password-input'],
    },
  ],
}
function validatePasswordStartWith(rule, value) {
  return (
    !!passwordForm.value.new_password &&
    passwordForm.value.new_password.startsWith(value) &&
    passwordForm.value.new_password.length >= value.length
  )
}
function validatePasswordSame(rule, value) {
  return value === passwordForm.value.new_password
}

// 零成本 TOTP 二次验证（Google Authenticator 等：扫码 otpauth URI）
const totpEnabled = ref(!!userStore.userInfo?.totp_enabled)
const totpSecret = ref('')
const totpUri = ref('')
const totpQrDataUrl = ref('')
const totpCode = ref('')
const totpDisablePassword = ref('')
const totpDisableCode = ref('')
const recoveryQuestionSet = ref(false)
const recoveryQuestion = ref('')
const recoveryAnswer = ref('')
const recoveryTotpCode = ref('')

function clearTotpSetupUi() {
  totpCode.value = ''
  totpSecret.value = ''
  totpUri.value = ''
  totpQrDataUrl.value = ''
}

async function refreshTotpStatus() {
  try {
    const res = await api.getUserInfo()
    totpEnabled.value = !!res.data?.totp_enabled
    recoveryQuestionSet.value = !!res.data?.recovery_question_set
  } catch (e) {
    /* ignore */
  }
}

async function startTotpSetup() {
  isLoading.value = true
  try {
    const res = await api.totpSetup()
    totpSecret.value = res.data?.secret || ''
    totpUri.value = res.data?.otpauth_uri || ''
    totpQrDataUrl.value = ''
    if (totpUri.value) {
      try {
        // 本机生成二维码，密钥不发往第三方图床
        const QRCode = (await import('qrcode')).default
        totpQrDataUrl.value = await QRCode.toDataURL(totpUri.value, {
          width: 260,
          margin: 2,
          errorCorrectionLevel: 'M',
        })
      } catch (qrErr) {
        console.warn('QR generate failed, fallback to manual secret', qrErr)
      }
    }
    $message.success(
      totpQrDataUrl.value
        ? '请用 Google Authenticator 等 App 扫码绑定'
        : '二维码生成失败，请手动输入下方密钥'
    )
  } catch (e) {
    /* handled */
  }
  isLoading.value = false
}

async function confirmTotp() {
  if (!/^\d{6}$/.test(totpCode.value)) {
    $message.warning('请输入验证器中的 6 位动态码')
    return
  }
  if (recoveryQuestion.value.trim().length < 4) {
    $message.warning('安全问题至少需要 4 个字符')
    return
  }
  if (recoveryAnswer.value.trim().length < 8) {
    $message.warning('安全答案至少需要 8 个字符')
    return
  }
  isLoading.value = true
  try {
    await api.totpConfirm({
      code: totpCode.value,
      secret: totpSecret.value,
      recovery_question: recoveryQuestion.value.trim(),
      recovery_answer: recoveryAnswer.value,
    })
    removeToken()
    $message.success('动态验证器与安全问题已启用，请重新登录')
    clearTotpSetupUi()
    router.replace('/login')
  } catch (e) {
    /* handled */
  } finally {
    isLoading.value = false
  }
}

async function saveRecoveryQuestion() {
  if (recoveryQuestion.value.trim().length < 4) {
    $message.warning('安全问题至少需要 4 个字符')
    return
  }
  if (recoveryAnswer.value.trim().length < 8) {
    $message.warning('安全答案至少需要 8 个字符')
    return
  }
  if (!/^\d{6}$/.test(recoveryTotpCode.value)) {
    $message.warning('请输入当前验证器中的 6 位动态码')
    return
  }
  isLoading.value = true
  try {
    await api.setTotpRecoveryQuestion({
      question: recoveryQuestion.value.trim(),
      answer: recoveryAnswer.value,
      totp_code: recoveryTotpCode.value,
    })
    removeToken()
    $message.success('安全问题已保存，请使用动态验证码重新登录')
    router.replace('/login')
  } catch (e) {
    /* handled */
  } finally {
    isLoading.value = false
  }
}

async function disableTotp() {
  if (!totpDisablePassword.value || !totpDisableCode.value) {
    $message.warning('请填写密码与验证码')
    return
  }
  isLoading.value = true
  try {
    await api.totpDisable({
      password: totpDisablePassword.value,
      code: totpDisableCode.value,
    })
    removeToken()
    $message.success('二次验证已关闭，请重新登录')
    totpDisablePassword.value = ''
    totpDisableCode.value = ''
    router.replace('/login')
  } catch (e) {
    /* handled */
  }
  isLoading.value = false
}

onMounted(() => {
  if (!isForceChange.value || isRestrictedSecurity.value) refreshTotpStatus()
})
</script>

<template>
  <CommonPage :show-header="false">
    <NTabs v-model:value="profileTab" type="line" animated>
      <NTabPane v-if="!isForceChange && !isRestrictedSecurity" name="website" :tab="$t('views.profile.label_modify_information')">
        <div class="m-30 flex items-center">
          <NForm
            ref="infoFormRef"
            label-placement="left"
            label-align="left"
            label-width="100"
            :model="infoForm"
            :rules="infoFormRules"
            class="w-400"
          >
            <NFormItem :label="$t('views.profile.label_avatar')" path="avatar">
              <NImage width="100" :src="infoForm.avatar"></NImage>
            </NFormItem>
            <NFormItem :label="$t('views.profile.label_username')" path="username">
              <NInput
                v-model:value="infoForm.username"
                type="text"
                :placeholder="$t('views.profile.placeholder_username')"
              />
            </NFormItem>
            <NFormItem :label="$t('views.profile.label_email')" path="email">
              <NInput
                v-model:value="infoForm.email"
                type="text"
                :placeholder="$t('views.profile.placeholder_email')"
              />
            </NFormItem>
            <NButton type="primary" :loading="isLoading" @click="updateProfile">
              {{ $t('common.buttons.update') }}
            </NButton>
          </NForm>
        </div>
      </NTabPane>
      <NTabPane v-if="!isTotpRecovery" name="contact" :tab="$t('views.profile.label_change_password')">
        <NForm
          ref="passwordFormRef"
          label-placement="left"
          label-align="left"
          :model="passwordForm"
          label-width="200"
          :rules="passwordFormRules"
          class="m-30 w-500"
        >
          <NFormItem :label="$t('views.profile.label_old_password')" path="old_password">
            <NInput
              v-model:value="passwordForm.old_password"
              type="password"
              show-password-on="mousedown"
              :placeholder="$t('views.profile.placeholder_old_password')"
            />
          </NFormItem>
          <NFormItem :label="$t('views.profile.label_new_password')" path="new_password">
            <NInput
              v-model:value="passwordForm.new_password"
              :disabled="!passwordForm.old_password"
              type="password"
              show-password-on="mousedown"
              :placeholder="$t('views.profile.placeholder_new_password')"
            />
          </NFormItem>
          <NFormItem :label="$t('views.profile.label_confirm_password')" path="confirm_password">
            <NInput
              v-model:value="passwordForm.confirm_password"
              :disabled="!passwordForm.new_password"
              type="password"
              show-password-on="mousedown"
              :placeholder="$t('views.profile.placeholder_confirm_password')"
            />
          </NFormItem>
          <NButton type="primary" :loading="isLoading" @click="updatePassword">
            {{ $t('common.buttons.update') }}
          </NButton>
        </NForm>
      </NTabPane>
      <NTabPane name="totp" tab="二次验证（TOTP）">
        <div class="m-30 w-560">
          <NAlert v-if="isRestrictedSecurity" type="warning" class="mb-16">
            当前是受限安全设置会话。完成动态验证器绑定和安全问题后，必须重新登录才能进入系统。
          </NAlert>
          <NAlert v-if="!totpEnabled" type="success" class="mb-16">
            <p><strong>第一次绑定（约 1 分钟）</strong></p>
            <ol class="totp-wizard">
              <li>手机安装 Google Authenticator（下方有苹果/安卓官方下载）</li>
              <li>点「开始绑定」，用手机 App 扫描二维码（密钥只在本机画图，不会预置进仓库）</li>
              <li>自定义安全问题与答案，再填 App 里的 6 位动态码</li>
            </ol>
          </NAlert>
          <NAlert type="info" class="mb-16">
            使用 <strong>Google Authenticator</strong>：点「开始绑定」后用<strong>手机扫下方二维码</strong>，再填 App
            里的 6 位动态码完成启用。密钥仅在本机生成二维码，不会上传第三方。
          </NAlert>
          <AuthenticatorDownloadLinks class="mb-16" />
          <p class="mb-12">
            当前状态：
            <strong>{{ totpEnabled ? '已启用' : '未启用' }}</strong>
          </p>
          <template v-if="!totpEnabled">
            <NButton type="primary" :loading="isLoading" class="mb-12" @click="startTotpSetup">
              开始绑定（生成二维码）
            </NButton>
            <div v-if="totpSecret" class="mb-12">
              <div v-if="totpQrDataUrl" class="totp-qr-wrap mb-12">
                <p class="mb-8"><strong>1. 打开验证器 App → 扫描二维码</strong></p>
                <img
                  :src="totpQrDataUrl"
                  alt="TOTP 绑定二维码"
                  width="260"
                  height="260"
                  class="totp-qr-img"
                  draggable="false"
                />
              </div>
              <details class="mb-12">
                <summary style="cursor: pointer; color: #666">扫不了？展开手动输入密钥</summary>
                <p class="mt-8">密钥（Base32）：</p>
                <code style="word-break: break-all; user-select: all">{{ totpSecret }}</code>
                <p class="mt-8" style="color: #888; font-size: 12px; word-break: break-all">
                  otpauth：{{ totpUri }}
                </p>
              </details>
              <p class="mb-8"><strong>2. 设置找回安全问题</strong></p>
              <NFormItem label="安全问题">
                <NInput
                  v-model:value="recoveryQuestion"
                  placeholder="例如：我的 Steam 号是多少？"
                  maxlength="120"
                />
              </NFormItem>
              <NFormItem label="安全答案">
                <NInput
                  v-model:value="recoveryAnswer"
                  type="password"
                  show-password-on="mousedown"
                  placeholder="至少 8 个字符"
                  maxlength="128"
                />
              </NFormItem>
              <p class="mb-8"><strong>3. 输入 App 显示的 6 位验证码</strong></p>
              <NFormItem label="验证码">
                <NInput
                  v-model:value="totpCode"
                  placeholder="App 中 6 位动态码"
                  :maxlength="6"
                  :allow-input="(value) => /^\d*$/.test(value)"
                  inputmode="numeric"
                  style="max-width: 240px"
                />
              </NFormItem>
              <NButton type="success" :loading="isLoading" @click="confirmTotp">
                确认启用并重新登录
              </NButton>
            </div>
          </template>
          <template v-else>
            <NFormItem label="登录密码">
              <NInput
                v-model:value="totpDisablePassword"
                type="password"
                show-password-on="mousedown"
                placeholder="当前密码"
              />
            </NFormItem>
            <NFormItem label="验证码">
              <NInput
                v-model:value="totpDisableCode"
                placeholder="App 中 6 位动态码"
                :maxlength="6"
                :allow-input="(value) => /^\d*$/.test(value)"
                inputmode="numeric"
              />
            </NFormItem>
            <NButton type="warning" :loading="isLoading" @click="disableTotp">关闭二次验证</NButton>
          </template>
          <NCard v-if="totpEnabled && !recoveryQuestionSet" size="small" title="设置找回安全问题" class="mt-16">
            <NAlert type="warning" class="mb-12">
              问题和答案由你自定义。找回时仍同时验证登录密码和滑块；连续 5 次错误会锁定 30 分钟。
            </NAlert>
            <NFormItem label="安全问题">
              <NInput v-model:value="recoveryQuestion" placeholder="例如：我的 Steam 号是多少？" maxlength="120" />
            </NFormItem>
            <NFormItem label="安全答案">
              <NInput
                v-model:value="recoveryAnswer"
                type="password"
                show-password-on="mousedown"
                placeholder="至少 8 个字符"
                maxlength="128"
              />
            </NFormItem>
            <NFormItem label="当前动态码">
              <NInput
                v-model:value="recoveryTotpCode"
                placeholder="验证器 6 位动态码"
                :maxlength="6"
                :allow-input="(value) => /^\d*$/.test(value)"
                inputmode="numeric"
                style="max-width: 240px"
              />
            </NFormItem>
            <NButton type="primary" :loading="isLoading" @click="saveRecoveryQuestion">
              保存并重新登录
            </NButton>
          </NCard>
          <NAlert v-else-if="totpEnabled && recoveryQuestionSet" type="success" class="mt-16">
            动态验证器与找回安全问题均已配置。
          </NAlert>
        </div>
      </NTabPane>
    </NTabs>
  </CommonPage>
</template>

<style scoped>
.totp-wizard {
  margin: 8px 0 0;
  padding-left: 20px;
  line-height: 1.7;
}
.totp-qr-wrap {
  display: inline-block;
  padding: 12px;
  background: #fff;
  border: 1px solid #e5e5e5;
  border-radius: 8px;
}
.totp-qr-img {
  display: block;
  background: #fff;
}
.mb-8 {
  margin-bottom: 8px;
}
.mb-12 {
  margin-bottom: 12px;
}
.mb-16 {
  margin-bottom: 16px;
}
.mt-8 {
  margin-top: 8px;
}
</style>
