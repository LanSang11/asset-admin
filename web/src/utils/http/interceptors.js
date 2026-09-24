import { getToken } from '@/utils'
import { resolveResError } from './helpers'
import { formatValidationMessage } from './validation-errors'
import { useUserStore } from '@/store'

export function reqResolve(config) {
  // 处理不需要token的请求
  if (config.noNeedToken) {
    return config
  }

  const token = getToken()
  if (token) {
    config.headers.token = config.headers.token || token
  }

  return config
}

export function reqReject(error) {
  return Promise.reject(error)
}

function isTotpChallenge(payload) {
  const body = payload?.data && typeof payload.data === 'object' ? payload.data : payload
  return !!(body?.totp_challenge || payload?.totp_challenge)
}

export function resResolve(response) {
  const { data, status, statusText } = response
  if (data?.code !== 200) {
    const code = data?.code ?? status
    /** 根据code处理对应的操作，并返回处理后的message */
    const message =
      code === 422
        ? formatValidationMessage(data, response.config?.url)
        : resolveResError(code, data?.msg ?? statusText)
    // 登录第二步：密码已通过，不要弹红字「失败」
    const notified = !response.config?.silent && !isTotpChallenge(data)
    if (notified) {
      window.$message?.error(message, { keepAliveOnHover: true })
    }
    return Promise.reject({ code, message, notified, error: data || response })
  }
  return Promise.resolve(data)
}

// 修复：401 并发防抖——多个请求同时 401 时只登出一次，
// 避免重复弹"登录已过期"、重复跳转
let isLoggingOut = false

export async function resReject(error) {
  if (!error || !error.response) {
    const code = error?.code
    /** 根据code处理对应的操作，并返回处理后的message */
    const message = resolveResError(code, error.message)
    const notified = !error?.config?.silent
    if (notified) {
      window.$message?.error(message)
    }
    return Promise.reject({ code, message, notified, error })
  }
  const { data, status, config } = error.response

  if (data?.code === 401) {
    try {
      if (!isLoggingOut) {
        isLoggingOut = true
        // 修复：401 防抖内只提示一次（原并发 401 重复弹窗；现完全不弹也无反馈）
        window.$message?.error('登录已过期，请重新登录')
        const userStore = useUserStore()
        await userStore.logout()
        setTimeout(() => {
          isLoggingOut = false
        }, 3000)
      }
    } catch (error) {
      console.log('resReject error', error)
      return
    }
    // 修复：401 处理完直接返回（原继续走下方弹窗逻辑，重复弹"登录已过期"）
    return Promise.reject({
      code: 401,
      message: '登录已过期',
      notified: true,
      error: data || error.response,
    })
  }
  // 后端返回的response数据
  const code = data?.code ?? status
  const message =
    code === 422
      ? formatValidationMessage(data, config?.url)
      : resolveResError(code, data?.msg ?? error.message)
  const notified = !config?.silent && !isTotpChallenge(data)
  if (notified) {
    window.$message?.error(message, { keepAliveOnHover: true })
  }
  return Promise.reject({ code, message, notified, error: error.response?.data || error.response })
}
