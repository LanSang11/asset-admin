import { defineStore } from 'pinia'
import { basicRoutes, vueModules } from '@/router/routes'
import Layout from '@/layout/index.vue'
import api from '@/api'
import { useUserStore } from '../user'

// * 后端路由相关函数
// 根据后端传来数据构建出前端路由

function buildRoutes(routes = []) {
  return routes.map((e) => {
    const route = {
      name: e.name,
      path: e.path,
      component: shallowRef(Layout),
      isHidden: e.is_hidden,
      redirect: e.redirect,
      meta: {
        title: e.name,
        icon: e.icon,
        order: e.order,
        keepAlive: e.keepalive,
        portal: 'admin',
      },
      children: [],
    }

    if (e.children && e.children.length > 0) {
      // 有子菜单
      route.children = e.children.map((e_child) => ({
        name: e_child.name,
        path: e_child.path,
        component: vueModules[`/src/views${e_child.component}/index.vue`],
        isHidden: e_child.is_hidden,
        meta: {
          title: e_child.name,
          icon: e_child.icon,
          order: e_child.order,
          keepAlive: e_child.keepalive,
        },
      }))
    } else {
      // 没有子菜单，创建一个默认的子路由
      route.children.push({
        name: `${e.name}Default`,
        path: '',
        component: vueModules[`/src/views${e.component}/index.vue`],
        isHidden: true,
        meta: {
          title: e.name,
          icon: e.icon,
          order: e.order,
          keepAlive: e.keepalive,
        },
      })
    }

    return route
  })
}

export const usePermissionStore = defineStore('permission', {
  state() {
    return {
      accessRoutes: [],
      accessApis: [],
    }
  },
  getters: {
    routes() {
      return basicRoutes.concat(this.accessRoutes)
    },
    menus() {
      const userStore = useUserStore()
      // 管理后台侧栏：隐藏工作台专用路由；员工壳用 WorkSideMenu，不走这里
      return this.routes.filter((route) => {
        if (!route.name || route.isHidden) return false
        if (route.meta?.portal === 'work') return false
        // 工作台用户若误入管理 Layout，不展示管理菜单
        if (userStore.portal === 'work') return false
        return true
      })
    },
    apis() {
      return this.accessApis
    },
  },
  actions: {
    async generateRoutes() {
      const userStore = useUserStore()
      const portal = userStore.portal
      const res = await api.getUserMenu()
      // 方案 B：管理后台挂载动态菜单；工作台用户仅用 /work 静态入口，不挂管理壳路由
      if (portal === 'admin') {
        this.accessRoutes = buildRoutes(res.data || [])
      } else {
        this.accessRoutes = []
      }
      return this.accessRoutes
    },
    async getAccessApis() {
      const res = await api.getUserApi()
      this.accessApis = res.data || []
      return this.accessApis
    },
    resetPermission() {
      this.$reset()
    },
  },
})
