import { createRouter, createWebHistory, createWebHashHistory } from 'vue-router'
import { setupRouterGuard } from './guard'
import { basicRoutes, EMPTY_ROUTE, NOT_FOUND_ROUTE } from './routes'
import { getToken, isNullOrWhitespace } from '@/utils'
import { useUserStore, usePermissionStore } from '@/store'

const isHash = import.meta.env.VITE_USE_HASH === 'true'
export const router = createRouter({
  history: isHash ? createWebHashHistory('/') : createWebHistory('/'),
  routes: basicRoutes,
  scrollBehavior: () => ({ left: 0, top: 0 }),
})

export async function setupRouter(app) {
  await addDynamicRoutes()
  setupRouterGuard(router)
  app.use(router)
}

export async function resetRouter() {
  const basicRouteNames = getRouteNames(basicRoutes)
  router.getRoutes().forEach((route) => {
    const name = route.name
    if (!basicRouteNames.includes(name)) {
      router.removeRoute(name)
    }
  })
}

export async function addDynamicRoutes() {
  const token = getToken()

  // 没有token情况
  if (isNullOrWhitespace(token)) {
    router.addRoute(EMPTY_ROUTE)
    return
  }
  // 有token的情况
  const userStore = useUserStore()
  const permissionStore = usePermissionStore()
  !userStore.userId && (await userStore.getUserInfo())
  if (userStore.userInfo?.security_setup_only || userStore.userInfo?.totp_recovery_only) {
    router.hasRoute(EMPTY_ROUTE.name) && router.removeRoute(EMPTY_ROUTE.name)
    return
  }
  try {
    const accessRoutes = await permissionStore.generateRoutes()
    await permissionStore.getAccessApis()
    accessRoutes.forEach((route) => {
      !router.hasRoute(route.name) && router.addRoute(route)
    })
    router.hasRoute(EMPTY_ROUTE.name) && router.removeRoute(EMPTY_ROUTE.name)
    router.addRoute(NOT_FOUND_ROUTE)
  } catch (error) {
    console.error('error', error)
    // 修复：仅认证失败（401）才强制登出；网络抖动/服务暂不可用等
    // 瞬时错误不应清空 token 把用户踢下线
    if (error?.code === 401 || error?.response?.status === 401) {
      const userStore = useUserStore()
      await userStore.logout()
    }
  }
}

export function getRouteNames(routes) {
  return routes.map((route) => getRouteName(route)).flat(1)
}

function getRouteName(route) {
  const names = [route.name]
  if (route.children && route.children.length) {
    names.push(...route.children.map((item) => getRouteName(item)).flat(1))
  }
  return names
}
