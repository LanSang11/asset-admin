import i18n from '~/i18n'
const { t } = i18n.global

const Layout = () => import('@/layout/index.vue')
const WorkLayout = () => import('@/layout/work/index.vue')

export const basicRoutes = [
  {
    path: '/',
    name: 'RootPortal',
    isHidden: true,
    // 禁止写死 redirect:/workbench（会先于守卫把 / 收成管理端，PORTAL-WB-1）
    // 落点只由 auth-guard → getHomePath(portal) 决定
    component: { render: () => null },
    meta: { order: 0 },
  },
  {
    name: t('views.workbench.label_workbench'),
    path: '/workbench',
    component: Layout,
    children: [
      {
        path: '',
        component: () => import('@/views/workbench/index.vue'),
        name: `${t('views.workbench.label_workbench')}Default`,
        meta: {
          title: t('views.workbench.label_workbench'),
          icon: 'icon-park-outline:workbench',
          affix: true,
        },
      },
    ],
    meta: { order: 1, portal: 'admin' },
  },
  // 方案 B：员工/主管工作台入口（同一后端，独立壳）
  {
    name: 'WorkPortal',
    path: '/work',
    component: WorkLayout,
    redirect: '/work/home',
    isHidden: true,
    meta: { order: 0, portal: 'work' },
    children: [
      {
        path: 'home',
        name: 'WorkHome',
        component: () => import('@/views/work/home/index.vue'),
        meta: {
          title: '我的工作台',
          icon: 'icon-park-outline:workbench',
          affix: true,
        },
      },
      {
        path: 'asset-use',
        name: 'WorkAssetUse',
        component: () => import('@/views/business/asset-use/index.vue'),
        meta: {
          title: '领用归还',
          icon: 'mdi:swap-horizontal',
        },
      },
      {
        path: 'approval',
        name: 'WorkApproval',
        component: () => import('@/views/business/approval/index.vue'),
        meta: {
          title: '审批中心',
          icon: 'mdi:clipboard-check-outline',
        },
      },
      {
        path: 'repair',
        name: 'WorkRepair',
        component: () => import('@/views/business/repair/index.vue'),
        meta: {
          title: '报修',
          icon: 'mdi:wrench-outline',
        },
      },
      {
        path: 'transfer',
        name: 'WorkTransfer',
        component: () => import('@/views/business/transfer/index.vue'),
        meta: {
          title: '调拨',
          icon: 'mdi:swap-horizontal-circle-outline',
        },
      },
      {
        path: 'inventory',
        name: 'WorkInventory',
        component: () => import('@/views/business/inventory/index.vue'),
        meta: {
          title: '盘点',
          icon: 'mdi:clipboard-text-outline',
        },
      },
      {
        path: 'my-assets',
        name: 'WorkMyAssets',
        component: () => import('@/views/work/my-assets/index.vue'),
        meta: {
          title: '我的资产',
          icon: 'mdi:desktop-classic',
        },
      },
      {
        path: 'dashboard',
        name: 'WorkDashboard',
        component: () => import('@/views/business/dashboard/index.vue'),
        meta: {
          title: '统计看板',
          icon: 'mdi:chart-box-outline',
        },
      },
      {
        path: 'ai',
        name: 'WorkAi',
        component: () => import('@/views/business/ai-assistant/index.vue'),
        meta: {
          title: 'AI 助手',
          icon: 'mdi:robot-outline',
        },
      },
      {
        path: 'kb',
        name: 'WorkKb',
        component: () => import('@/views/business/kb/index.vue'),
        meta: {
          title: '知识库',
          icon: 'mdi:book-open-page-variant-outline',
        },
      },
      {
        path: 'files',
        name: 'WorkFiles',
        component: () => import('@/views/work/files/index.vue'),
        meta: {
          title: '我的附件',
          icon: 'mdi:paperclip',
        },
      },

      {
        path: 'profile',
        name: 'WorkProfile',
        component: () => import('@/views/profile/index.vue'),
        meta: {
          title: '个人中心',
          icon: 'mdi:account-circle-outline',
        },
      },
    ],
  },
  {
    name: t('views.profile.label_profile'),
    path: '/profile',
    component: Layout,
    isHidden: true,
    children: [
      {
        path: '',
        component: () => import('@/views/profile/index.vue'),
        name: `${t('views.profile.label_profile')}Default`,
        meta: {
          title: t('views.profile.label_profile'),
          icon: 'user',
          affix: true,
        },
      },
    ],
    meta: { order: 99 },
  },
  {
    name: 'ErrorPage',
    path: '/error-page',
    component: Layout,
    redirect: '/error-page/404',
    meta: {
      title: t('views.errors.label_error'),
      icon: 'mdi:alert-circle-outline',
      order: 99,
    },
    children: [
      {
        name: 'ERROR-401',
        path: '401',
        component: () => import('@/views/error-page/401.vue'),
        meta: {
          title: '401',
          icon: 'material-symbols:authenticator',
        },
      },
      {
        name: 'ERROR-403',
        path: '403',
        component: () => import('@/views/error-page/403.vue'),
        meta: {
          title: '403',
          icon: 'solar:forbidden-circle-line-duotone',
        },
      },
      {
        name: 'ERROR-404',
        path: '404',
        component: () => import('@/views/error-page/404.vue'),
        meta: {
          title: '404',
          icon: 'tabler:error-404',
        },
      },
      {
        name: 'ERROR-500',
        path: '500',
        component: () => import('@/views/error-page/500.vue'),
        meta: {
          title: '500',
          icon: 'clarity:rack-server-outline-alerted',
        },
      },
    ],
  },
  {
    name: '403',
    path: '/403',
    component: () => import('@/views/error-page/403.vue'),
    isHidden: true,
  },
  {
    name: '404',
    path: '/404',
    component: () => import('@/views/error-page/404.vue'),
    isHidden: true,
  },
  {
    name: 'Login',
    path: '/login',
    component: () => import('@/views/login/index.vue'),
    isHidden: true,
    meta: {
      title: '登录页',
    },
  },
  {
    name: 'AssetScan',
    path: '/q/:assetNo',
    component: () => import('@/views/scan/index.vue'),
    isHidden: true,
    meta: {
      title: '资产扫码',
    },
  },
]

export const NOT_FOUND_ROUTE = {
  name: 'NotFound',
  path: '/:pathMatch(.*)*',
  redirect: '/404',
  isHidden: true,
}

export const EMPTY_ROUTE = {
  name: 'Empty',
  path: '/:pathMatch(.*)*',
  component: null,
}

const modules = import.meta.glob('@/views/**/route.js', { eager: true })
const asyncRoutes = []
Object.keys(modules).forEach((key) => {
  asyncRoutes.push(modules[key].default)
})

// 加载 views 下每个模块的 index.vue 文件
const vueModules = import.meta.glob('@/views/**/index.vue')

export { asyncRoutes, vueModules }
