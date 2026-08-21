const EXTERNAL_PATH_PATTERN = /^(?:(?:https?:)?\/\/|https?:|mailto:|tel:)/i

function isExternalMenuPath(path) {
  return typeof path === 'string' && EXTERNAL_PATH_PATTERN.test(path)
}

function getRouteIcon(route) {
  return {
    iconName: route?.meta?.icon ?? route?.icon,
    customIcon: route?.meta?.customIcon ?? route?.customIcon,
  }
}

function getRouteOrder(route) {
  return route?.meta?.order ?? route?.order ?? 0
}

function getVisibleChildren(route) {
  if (!Array.isArray(route?.children)) return []
  return route.children.filter((item) => item?.name && !item.isHidden)
}

function sortMenuModels(models) {
  return models.sort((a, b) => a.order - b.order)
}

export function resolveMenuPath(basePath = '', path = '') {
  const targetPath = String(path ?? '')
  if (isExternalMenuPath(targetPath)) return targetPath

  const segments = [basePath, targetPath]
    .filter((value) => value && value !== '/')
    .map((value) => String(value).replace(/(^\/)|(\/$)/g, ''))
    .filter(Boolean)

  return `/${segments.join('/')}`
}

function buildAdminMenuModel(route, basePath = '') {
  const routePath = resolveMenuPath(basePath, route.path)
  let menuModel = {
    label: route.meta?.title || route.label || route.name,
    key: route.name,
    path: routePath,
    ...getRouteIcon(route),
    order: getRouteOrder(route),
  }

  const visibleChildren = getVisibleChildren(route)
  if (!visibleChildren.length) return menuModel

  if (visibleChildren.length === 1) {
    const singleRoute = visibleChildren[0]
    menuModel = {
      ...menuModel,
      label: singleRoute.meta?.title || singleRoute.label || singleRoute.name,
      key: singleRoute.name,
      path: resolveMenuPath(menuModel.path, singleRoute.path),
      ...getRouteIcon(singleRoute),
    }

    const visibleItems = getVisibleChildren(singleRoute)
    if (visibleItems.length === 1) {
      return buildAdminMenuModel(visibleItems[0], menuModel.path)
    }
    if (visibleItems.length > 1) {
      menuModel.children = sortMenuModels(
        visibleItems.map((item) => buildAdminMenuModel(item, menuModel.path))
      )
    }
    return menuModel
  }

  menuModel.children = sortMenuModels(
    visibleChildren.map((item) => buildAdminMenuModel(item, menuModel.path))
  )
  return menuModel
}

export function buildAdminMenuModels(routes = [], basePath = '') {
  if (!Array.isArray(routes)) return []
  return sortMenuModels(
    routes
      .filter((route) => route?.name && !route.isHidden)
      .map((route) => buildAdminMenuModel(route, basePath))
  )
}

const WORK_MENU_DEFINITIONS = [
  {
    label: '我的工作台',
    key: 'WorkHome',
    path: '/work/home',
    iconName: 'icon-park-outline:workbench',
    order: 1,
  },
  {
    label: '领用归还',
    key: 'WorkAssetUse',
    path: '/work/asset-use',
    iconName: 'mdi:swap-horizontal',
    order: 2,
    anyOf: ['post/api/v1/asset-use/apply', 'get/api/v1/asset-use/list'],
  },
  {
    label: '我的资产',
    key: 'WorkMyAssets',
    path: '/work/my-assets',
    iconName: 'mdi:desktop-classic',
    order: 3,
    anyOf: ['get/api/v1/asset/my'],
  },
  {
    label: '审批中心',
    key: 'WorkApproval',
    path: '/work/approval',
    iconName: 'mdi:clipboard-check-outline',
    order: 4,
    anyOf: ['post/api/v1/asset-use/approve'],
  },
  {
    label: '报修',
    key: 'WorkRepair',
    path: '/work/repair',
    iconName: 'mdi:wrench-outline',
    order: 4.5,
    anyOf: ['post/api/v1/asset-repair/apply', 'get/api/v1/asset-repair/list'],
  },
  {
    label: '调拨',
    key: 'WorkTransfer',
    path: '/work/transfer',
    iconName: 'mdi:swap-horizontal-circle-outline',
    order: 4.6,
    anyOf: ['post/api/v1/asset-transfer/apply', 'get/api/v1/asset-transfer/list'],
  },
  {
    label: '盘点',
    key: 'WorkInventory',
    path: '/work/inventory',
    iconName: 'mdi:clipboard-text-outline',
    order: 4.7,
    anyOf: ['get/api/v1/inventory/list', 'post/api/v1/inventory/count'],
  },
  {
    label: '统计看板',
    key: 'WorkDashboard',
    path: '/work/dashboard',
    iconName: 'mdi:chart-box-outline',
    order: 5,
    anyOf: ['get/api/v1/dashboard/stats'],
  },
  {
    label: 'AI 助手',
    key: 'WorkAi',
    path: '/work/ai',
    iconName: 'mdi:robot-outline',
    order: 6,
    anyOf: ['post/api/v1/ai/chat'],
  },
  {
    label: '知识库',
    key: 'WorkKb',
    path: '/work/kb',
    iconName: 'mdi:book-open-page-variant-outline',
    order: 6.5,
    anyOf: ['post/api/v1/kb/ask', 'get/api/v1/kb/list'],
  },
  {
    label: '我的附件',
    key: 'WorkFiles',
    path: '/work/files',
    iconName: 'mdi:paperclip',
    order: 6.6,
    anyOf: ['post/api/v1/employee-attachment/upload', 'get/api/v1/employee-attachment/list'],
  },
  {
    label: '个人中心',
    key: 'WorkProfile',
    path: '/work/profile',
    iconName: 'mdi:account-circle-outline',
    order: 99,
  },
]

export function buildWorkMenuModels(accessApis = []) {
  const apiSet = new Set(Array.isArray(accessApis) ? accessApis : [])
  return WORK_MENU_DEFINITIONS.filter(
    (item) => !item.anyOf || item.anyOf.some((permission) => apiSet.has(permission))
  )
    .map((item) => ({
      label: item.label,
      key: item.key,
      path: item.path,
      iconName: item.iconName,
      order: item.order,
    }))
    .sort((a, b) => a.order - b.order)
}

export function getActiveMenuKey(route) {
  return route?.meta?.activeMenu || route?.name || null
}

export async function navigateMenuModel(model, { router, route, reloadPage, openExternal } = {}) {
  const path = model?.path
  if (!path) return

  if (isExternalMenuPath(path)) {
    const open =
      openExternal ||
      (typeof window !== 'undefined' && typeof window.open === 'function'
        ? window.open.bind(window)
        : null)
    open?.(path, '_blank', 'noopener,noreferrer')
    return
  }

  if (path === route?.path) {
    await reloadPage?.()
    return
  }

  await router?.push?.(path)
}
