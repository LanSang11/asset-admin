/**
 * 方案 B：入口分流（admin=管理后台，work=员工/主管工作台）
 */

export function resolvePortal(userInfo = {}) {
  if (userInfo?.portal === 'admin' || userInfo?.portal === 'work') {
    return userInfo.portal
  }
  if (userInfo?.is_superuser) return 'admin'
  const roleNames = userInfo?.role_names
    || (userInfo?.roles || []).map((r) => (typeof r === 'string' ? r : r?.name)).filter(Boolean)
  if (roleNames.includes('管理员')) return 'admin'
  return 'work'
}

/** 登录后默认首页 */
export function getHomePath(portal) {
  return portal === 'admin' ? '/workbench' : '/work/home'
}

/**
 * 员工/主管是否允许访问该 path（管理后台路由一律禁止）
 * 管理员可访问全部（含 /work 预览）
 *
 * 禁止用「/work」当前缀做 startsWith：会把 /workbench 误判成工作台（PORTAL-WB-1）
 */
export function canWorkUserAccessPath(path = '') {
  if (!path) return false
  const p = path.split('?')[0]
  if (p === '/login' || p === '/404' || p === '/403') return true
  if (p === '/profile') return true // 强制改密等
  if (p === '/q' || p.startsWith('/q/')) return true // 手机扫资产码
  if (p === '/work' || p.startsWith('/work/')) return true
  if (p.startsWith('/error-page')) return true
  return false
}

/** 管理端专属路径前缀（员工直输 URL 应拦截） */
export const ADMIN_ONLY_PATH_PREFIXES = [
  '/workbench',
  '/system',
  '/business',
]

/** 管理壳/站点根：work 用户应拉回工作台，不要停在空壳 */
export function isAdminLandingPath(path = '') {
  const p = String(path || '').split('?')[0]
  if (p === '/') return true
  return ADMIN_ONLY_PATH_PREFIXES.some((prefix) => p === prefix)
}
