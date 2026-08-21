/**
 * 文件下载工具（导出功能用）
 * 直接调 axios 以 blob 方式下载，支持中文文件名
 */
import axios from 'axios'
import { getToken } from './auth'
import { ensureStepUpToken } from '@/composables/useStepUp'

/**
 * 下载导出文件
 * @param url 接口路径（相对 /api/v1）
 * @param params 查询参数
 * @param filename 下载文件名
 * @param operationKey 二次验证操作键
 */
export async function downloadFile(url, params = {}, filename = 'export.csv', operationKey = '') {
  const stepUpToken = operationKey ? await ensureStepUpToken(operationKey) : ''
  const headers = { token: getToken() }
  if (stepUpToken) headers['X-Step-Up-Token'] = stepUpToken
  const res = await axios.get(`/api/v1${url}`, {
    params,
    responseType: 'blob',
    headers,
  })
  // 从响应头取文件名（有则用，无则用默认）
  const disposition = res.headers['content-disposition']
  let realName = filename
  if (disposition) {
    const match = disposition.match(/filename="?([^";]+)"?/)
    if (match) realName = decodeURIComponent(match[1])
  }
  const blob = new Blob([res.data])
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = realName
  link.click()
  URL.revokeObjectURL(link.href)
}
