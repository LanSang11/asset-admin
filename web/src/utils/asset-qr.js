export const ASSET_QR_PATH_PREFIX = '/q/'

const ASSET_ACTION_PATHS = {
  repair: {
    admin: '/business/repair',
    work: '/work/repair',
  },
  transfer: {
    admin: '/business/transfer',
    work: '/work/transfer',
  },
}

const ASSET_ACTION_APIS = {
  repair: 'post/api/v1/asset-repair/apply',
  transfer: 'post/api/v1/asset-transfer/apply',
}

export function assetScanPath(assetNo) {
  const no = String(assetNo || '').trim()
  if (!no) return ''
  return `${ASSET_QR_PATH_PREFIX}${encodeURIComponent(no)}`
}

export function assetScanUrl(assetNo, origin = '') {
  const path = assetScanPath(assetNo)
  if (!path) return ''
  const base = String(
    origin || (typeof window !== 'undefined' ? window.location.origin : '')
  ).replace(/\/$/, '')
  return `${base}${path}`
}

export function assetActionLocation(action, asset, portal = 'work') {
  const paths = ASSET_ACTION_PATHS[action]
  const id = Number(asset?.id)
  const assetNo = String(asset?.asset_no || '').trim()
  if (!paths || !Number.isInteger(id) || id <= 0 || !assetNo || Number(asset?.status) !== 1)
    return null
  return {
    path: portal === 'admin' ? paths.admin : paths.work,
    query: {
      asset_id: String(id),
      asset_no: assetNo,
    },
  }
}

export function canUseScanAction(
  action,
  asset,
  { accessApis = [], portal = 'work', ownAssetIds = [], hasActiveEmployee = false } = {}
) {
  const api = ASSET_ACTION_APIS[action]
  if (!api || !hasActiveEmployee || Number(asset?.status) !== 1 || !accessApis.includes(api))
    return false
  if (action === 'repair' || portal === 'admin') return true
  const assetId = Number(asset?.id)
  return ownAssetIds.some((id) => Number(id) === assetId)
}

export function resolveScannedAsset(assets, query = {}) {
  const assetId = Number(Array.isArray(query.asset_id) ? query.asset_id[0] : query.asset_id)
  const assetNo = String(
    (Array.isArray(query.asset_no) ? query.asset_no[0] : query.asset_no) || ''
  ).trim()
  if (!Number.isInteger(assetId) || assetId <= 0 || !assetNo) return null
  return (
    (Array.isArray(assets) ? assets : []).find(
      (asset) => Number(asset?.id) === assetId && String(asset?.asset_no || '').trim() === assetNo
    ) || null
  )
}

export function scanAssetStatusNotice(status) {
  const notices = {
    2: '这台资产当前处于闲置状态，暂不能发起报修或调拨。',
    3: '这台资产正在维修中，请等待维修完成后再操作。',
    4: '这台资产已经报废，只能查看信息，不能发起报修或调拨。',
  }
  if (Number(status) === 1) return ''
  return notices[Number(status)] || '这台资产的状态异常，请联系管理员核对后再操作。'
}
