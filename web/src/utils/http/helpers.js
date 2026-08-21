import { useUserStore } from '@/store'

export function addBaseParams(params) {
  if (!params.userId) {
    params.userId = useUserStore().userId
  }
}

export function resolveResError(code, message) {
  switch (code) {
    case 400:
      message = message ?? '请求参数错误'
      break
    case 401:
      message = message ?? '登录已过期'
      break
    case 403:
      // 方案 D 兜底：若后端仍回英文/path，前端不向用户展示侦察信息
      if (
        message
        && (/Permission\s*denied|method\s*:|path\s*:|\/api\/v1/i.test(String(message)))
      ) {
        message = '暂无权限执行此操作，如需开通请联系系统管理员。'
      }
      message = message ?? '暂无权限执行此操作，如需开通请联系系统管理员。'
      break
    case 404:
      message = message ?? '资源或接口不存在'
      break
    case 429:
      // 修复：限流/黑名单专用文案（原无此分支，显示"【429】未知异常"）
      message = message ?? '操作过于频繁，请稍后再试'
      break
    case 500:
      message = message ?? '服务器异常'
      break
    default:
      message = message ?? `【${code}】: 未知异常!`
      break
  }
  return message
}
