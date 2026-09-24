<template>
  <div class="root-portal-placeholder" aria-hidden="true" />
</template>

<script setup>
/**
 * 站点根占位：守卫应在渲染前把 `/` 收到 portal 首页。
 * 若导航被冲掉落到这里，不再渲染空白页，补一次 replace。
 */
import { getToken, getHomePath } from '@/utils'
import { useUserStore } from '@/store'

const router = useRouter()
const userStore = useUserStore()

onMounted(() => {
  if (!getToken()) {
    router.replace({ path: '/login', query: { redirect: '/' } })
    return
  }
  const here = router.currentRoute.value.path
  if (here !== '/') return
  router.replace(getHomePath(userStore.portal))
})
</script>
