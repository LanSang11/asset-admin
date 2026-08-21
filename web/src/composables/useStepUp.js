/**
 * Per-operation high-risk verification.
 */
import { h, ref } from 'vue'
import { NInput } from 'naive-ui'
import api from '@/api'

function promptCredential(mode) {
  return new Promise((resolve, reject) => {
    const value = ref('')
    const dialog = window.$dialog
    if (!dialog) {
      reject(new Error('对话框不可用'))
      return
    }
    let settled = false
    const isTotp = mode === 'totp'
    const d = dialog.create({
      title: '安全验证',
      content: () =>
        h('div', { style: 'padding-top: 8px' }, [
          h(
            'p',
            { style: 'margin-bottom: 12px; color: #666' },
            isTotp
              ? '此操作需要动态验证，请输入验证器 App 中的 6 位验证码。'
              : '此操作需要身份确认，请输入当前登录密码。'
          ),
          h(NInput, {
            type: isTotp ? 'text' : 'password',
            showPasswordOn: isTotp ? undefined : 'mousedown',
            placeholder: isTotp ? '6 位动态码' : '登录密码',
            maxlength: isTotp ? 6 : 128,
            allowInput: isTotp ? (text) => /^\d*$/.test(text) : undefined,
            inputmode: isTotp ? 'numeric' : undefined,
            value: value.value,
            'onUpdate:value': (next) => {
              value.value = next
            },
            onKeyup: (event) => {
              if (event.key === 'Enter') d.positiveClick?.()
            },
          }),
        ]),
      positiveText: '确认',
      negativeText: '取消',
      onPositiveClick: () => {
        if (!value.value) {
          window.$message?.warning(isTotp ? '请输入动态验证码' : '请输入密码')
          return false
        }
        settled = true
        resolve(value.value)
        return true
      },
      onNegativeClick: () => {
        settled = true
        reject(new Error('已取消'))
      },
      onClose: () => {
        if (!settled) reject(new Error('已取消'))
      },
    })
  })
}

export async function getStepUpRequirement(operationKey) {
  const res = await api.getStepUpRequirement({ operation_key: operationKey })
  return res.data || {}
}

export async function ensureStepUpToken(operationKey) {
  const requirement = await getStepUpRequirement(operationKey)
  const mode = requirement.mode || 'off'
  if (mode === 'off') return ''
  if (mode === 'totp' && !requirement.totp_enabled) {
    window.$message?.warning('当前账号尚未绑定动态验证器，请先到个人中心完成绑定')
    throw new Error('未绑定动态验证器')
  }
  const credential = await promptCredential(mode)
  const payload = { operation_key: operationKey }
  if (mode === 'totp') payload.totp_code = credential
  else payload.password = credential
  const res = await api.stepUp(payload)
  const token = res.data?.step_up_token
  if (!token) throw new Error('二次验证失败')
  return token
}

export async function withStepUp(operationKey, doRequest) {
  const token = await ensureStepUpToken(operationKey)
  const headers = token ? { 'X-Step-Up-Token': token } : {}
  return doRequest(headers)
}

export default { ensureStepUpToken, withStepUp, getStepUpRequirement }
