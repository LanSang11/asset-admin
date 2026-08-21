<template>
  <AppPage>
    <n-result
      m-auto
      status="403"
      title="暂无权限"
      description="您当前账号无权访问该页面。如需开通，请联系系统管理员。"
    >
      <template #footer>
        <n-button type="primary" @click="goHome">返回工作台</n-button>
      </template>
    </n-result>
  </AppPage>
</template>

<script setup>
import { useUserStore } from '@/store'
import { getHomePath } from '@/utils'

const router = useRouter()
const userStore = useUserStore()

function goHome() {
  router.replace(getHomePath(userStore.portal))
}
</script>
