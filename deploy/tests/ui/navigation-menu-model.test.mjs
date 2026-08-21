import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildAdminMenuModels,
  buildWorkMenuModels,
  getActiveMenuKey,
  navigateMenuModel,
  resolveMenuPath,
} from '../../../web/src/layout/navigation/menu-model.js'

test('resolveMenuPath 保持根路径、相对路径、绝对写法和外链语义', () => {
  assert.equal(resolveMenuPath(), '/')
  assert.equal(resolveMenuPath('', '/business'), '/business')
  assert.equal(resolveMenuPath('/business/', 'asset'), '/business/asset')
  assert.equal(resolveMenuPath('/business', '/asset'), '/business/asset')
  assert.equal(resolveMenuPath('/business', 'https://example.invalid/docs'), 'https://example.invalid/docs')
  assert.equal(resolveMenuPath('/business', '//example.invalid/docs'), '//example.invalid/docs')
  assert.equal(resolveMenuPath('/business', 'mailto:ops@example.invalid'), 'mailto:ops@example.invalid')
})

test('管理菜单过滤无名与隐藏路由，并按 order 排序', () => {
  const models = buildAdminMenuModels([
    { name: '后置', path: '/later', meta: { title: '后置', order: 20 } },
    { name: '隐藏', path: '/hidden', isHidden: true, meta: { order: 0 } },
    { path: '/nameless', meta: { order: 0 } },
    { name: '前置', path: '/first', meta: { title: '前置', order: 1 } },
  ])

  assert.deepEqual(models.map(({ key, path, order }) => ({ key, path, order })), [
    { key: '前置', path: '/first', order: 1 },
    { key: '后置', path: '/later', order: 20 },
  ])
})

test('管理菜单隐藏 isHidden 子项并保留 icon-park 图标名', () => {
  const models = buildAdminMenuModels([
    {
      name: '业务管理',
      path: '/business',
      meta: { title: '业务管理', order: 2, icon: 'mdi:briefcase' },
      children: [
        {
          name: '资产管理',
          path: 'asset',
          meta: { title: '资产管理', order: 1, icon: 'icon-park-outline:workbench' },
        },
        { name: '隐藏页', path: 'hidden', isHidden: true, meta: { title: '隐藏页' } },
      ],
    },
  ])

  assert.equal(models.length, 1)
  assert.equal(models[0].key, '资产管理')
  assert.equal(models[0].path, '/business/asset')
  assert.equal(models[0].iconName, 'icon-park-outline:workbench')
  assert.equal(models[0].order, 2)
  assert.equal(models[0].children, undefined)
})

test('管理菜单多子项递归生成、过滤隐藏项并按子项 order 排序', () => {
  const models = buildAdminMenuModels([
    {
      name: '业务管理',
      path: '/business',
      meta: { title: '业务管理', order: 2, customIcon: 'asset-mark' },
      children: [
        { name: '后置', path: '/later', meta: { title: '后置', order: 30 } },
        { name: '隐藏', path: 'hidden', isHidden: true, meta: { title: '隐藏', order: 0 } },
        { name: '前置', path: 'first', meta: { title: '前置', order: 1 } },
      ],
    },
  ])

  assert.equal(models[0].customIcon, 'asset-mark')
  assert.deepEqual(models[0].children.map(({ key, path }) => ({ key, path })), [
    { key: '前置', path: '/business/first' },
    { key: '后置', path: '/business/later' },
  ])
})

test('管理菜单连续单子路由按既有规则折叠到最深可见叶子', () => {
  const [model] = buildAdminMenuModels([
    {
      name: '父级',
      path: '/parent',
      meta: { title: '父级', order: 8 },
      children: [
        {
          name: '中间级',
          path: 'middle',
          meta: { title: '中间级', order: 7 },
          children: [
            {
              name: '叶子',
              path: 'leaf',
              meta: { title: '最终入口', icon: 'mdi:leaf', order: 6 },
            },
          ],
        },
      ],
    },
  ])

  assert.deepEqual(model, {
    label: '最终入口',
    key: '叶子',
    path: '/parent/middle/leaf',
    iconName: 'mdi:leaf',
    customIcon: undefined,
    order: 6,
  })
})

test('工作台员工菜单没有审批和系统管理，主管只额外出现审批', () => {
  const employee = buildWorkMenuModels([
    'get/api/v1/asset/my',
    'get/api/v1/asset-use/list',
    'get/api/v1/dashboard/stats',
  ])
  const manager = buildWorkMenuModels([
    'get/api/v1/asset/my',
    'get/api/v1/asset-use/list',
    'post/api/v1/asset-use/approve',
    'get/api/v1/dashboard/stats',
  ])

  assert.deepEqual(employee.map((item) => item.key), [
    'WorkHome',
    'WorkAssetUse',
    'WorkMyAssets',
    'WorkDashboard',
    'WorkProfile',
  ])
  assert.deepEqual(manager.map((item) => item.key), [
    'WorkHome',
    'WorkAssetUse',
    'WorkMyAssets',
    'WorkApproval',
    'WorkDashboard',
    'WorkProfile',
  ])
  assert.equal(employee.some((item) => /系统管理/.test(item.label)), false)
  assert.equal(manager.some((item) => /系统管理/.test(item.label)), false)
})

test('工作台权限使用精确 API 字符串，不因相似前缀扩大菜单', () => {
  const models = buildWorkMenuModels([
    'get/api/v1/asset/my-extra',
    'post/api/v1/asset-use/application',
    'get/api/v1/asset-repair/list-all',
    'post/api/v1/ai/chat-extra',
  ])

  assert.deepEqual(models.map((item) => item.key), ['WorkHome', 'WorkProfile'])
})

test('activeMenu 优先于路由 name，缺失时返回 null', () => {
  assert.equal(getActiveMenuKey({ name: 'AssetDetail', meta: { activeMenu: 'AssetList' } }), 'AssetList')
  assert.equal(getActiveMenuKey({ name: 'AssetList', meta: {} }), 'AssetList')
  assert.equal(getActiveMenuKey({}), null)
})

test('导航保持同页 reload、站内 push，外链使用 noopener,noreferrer', async () => {
  const calls = []
  const dependencies = {
    router: { push: async (path) => calls.push(['push', path]) },
    route: { path: '/current' },
    reloadPage: async () => calls.push(['reload']),
    openExternal: (...args) => calls.push(['open', ...args]),
  }

  await navigateMenuModel({ path: '/current' }, dependencies)
  await navigateMenuModel({ path: '/next' }, dependencies)
  await navigateMenuModel({ path: 'https://example.invalid' }, dependencies)
  await navigateMenuModel({}, dependencies)

  assert.deepEqual(calls, [
    ['reload'],
    ['push', '/next'],
    ['open', 'https://example.invalid', '_blank', 'noopener,noreferrer'],
  ])
})
