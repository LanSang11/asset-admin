import { getToken, isNullOrWhitespace, canWorkUserAccessPath, getHomePath, isAdminLandingPath } from '@/utils'
import { useUserStore } from '@/store'

const WHITE_LIST = ['/login', '/404', '/403']

export function createAuthGuard(router) {
  router.beforeEach(async (to) => {
    const token = getToken()

    /** 没有token的情况 */
    if (isNullOrWhitespace(token)) {
      if (WHITE_LIST.includes(to.path)) return true
      // 修复：redirect 带完整路径（含 query），登录后跳回原页面不丢参数
      return { path: 'login', query: { ...to.query, redirect: to.fullPath } }
    }

    const userStore = useUserStore()
    if (!userStore.userId) {
      try {
        await userStore.getUserInfo()
      } catch (_) {
        // getUserInfo 失败时后续接口会处理
      }
    }

    const portal = userStore.portal
    const home = getHomePath(portal)
    const restrictedSecurity =
      userStore.userInfo?.security_setup_only || userStore.userInfo?.totp_recovery_only

    /** 有token的情况 */
    if (restrictedSecurity) {
      if (to.path === '/profile') return true
      return {
        path: '/profile',
        query: userStore.userInfo?.totp_recovery_only
          ? { totpRecovery: '1' }
          : {
              securitySetup: '1',
              forceChangePassword: userStore.userInfo?.must_change_password ? '1' : undefined,
            },
      }
    }
    if (to.path === '/login') return { path: home }

    // 根路径只认 portal 首页，禁止写死管理端
    if (to.path === '/') return { path: home }

    // 方案 B：员工/主管禁止进入管理后台
    if (portal === 'work') {
      // 管理壳/默认落点拉回工作台，避免 /workbench 空壳
      if (isAdminLandingPath(to.path)) return { path: '/work/home' }
      // 直输更深管理路径（如 /system/*）给中文 403
      if (!canWorkUserAccessPath(to.path)) {
        return { path: '/403' }
      }
    }

    return true
  })
}
