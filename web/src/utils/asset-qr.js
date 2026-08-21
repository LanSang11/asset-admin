export const ASSET_QR_PATH_PREFIX = '/q/'

export function assetScanPath(assetNo) {
  const no = String(assetNo || '').trim()
  if (!no) return ''
  return `${ASSET_QR_PATH_PREFIX}${encodeURIComponent(no)}`
}

export function assetScanUrl(assetNo, origin = '') {
  const path = assetScanPath(assetNo)
  if (!path) return ''
  const base = String(origin || (typeof window !== 'undefined' ? window.location.origin : '')).replace(/\/$/, '')
  return `${base}${path}`
}
