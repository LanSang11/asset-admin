<template>
  <router-view v-slot="{ Component, route }">
    <KeepAlive :include="keepAliveRouteNames">
      <component
        :is="Component"
        v-if="appStore.reloadFlag"
        :key="appStore.aliveKeys[route.name] || route.fullPath"
      />
    </KeepAlive>
  </router-view>
</template>

<script setup>
import { useAppStore, usePermissionStore } from '@/store'
import { useRouter } from 'vue-router'
const appStore = useAppStore()
const permissionStore = usePermissionStore()
const router = useRouter()

// 修复：动态路由加入后 keep-alive 失效问题——
// 原实现对 router.getRoutes() 取一次性快照，动态路由（菜单权限路由）加入后
// keepAliveRouteNames 不更新，导致标签页切换时页面状态（查询条件/分页）丢失并重复请求。
// 通过依赖 permissionStore.accessRoutes（响应式）强制 computed 在动态路由变化后重算。
const keepAliveRouteNames = computed(() => {
  void permissionStore.accessRoutes.length
  return router.getRoutes().filter((route) => route.meta?.keepAlive).map((route) => route.name)
})
</script>
