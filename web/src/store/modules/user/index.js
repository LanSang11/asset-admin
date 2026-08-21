import { defineStore } from 'pinia'
import { resetRouter } from '@/router'
import { useTagsStore, usePermissionStore } from '@/store'
import { removeToken, toLogin, resolvePortal, getHomePath } from '@/utils'
import api from '@/api'

export const useUserStore = defineStore('user', {
  state() {
    return {
      userInfo: {},
    }
  },
  getters: {
    userId() {
      return this.userInfo?.id
    },
    name() {
      return this.userInfo?.username
    },
    email() {
      return this.userInfo?.email
    },
    avatar() {
      // 无个人头像时用原创默认头像（与右上角/工作台一致）
      const a = this.userInfo?.avatar
      if (a) return a
      return `${import.meta.env.BASE_URL}resource/default-avatar.jpg`
    },
    role() {
      return this.userInfo?.roles || []
    },
    isSuperUser() {
      return this.userInfo?.is_superuser
    },
    isActive() {
      return this.userInfo?.is_active
    },
    /** 方案 B：admin=管理后台，work=员工/主管工作台 */
    portal() {
      return resolvePortal(this.userInfo)
    },
    homePath() {
      return getHomePath(this.portal)
    },
  },
  actions: {
    async getUserInfo() {
      try {
        const res = await api.getUserInfo()
        if (res.code === 401) {
          this.logout()
          return
        }
        const {
          id,
          username,
          email,
          avatar,
          roles,
          is_superuser,
          is_active,
          portal,
          role_names,
          security_setup_only,
          totp_recovery_only,
          must_change_password,
          acceptance_mode,
        } = res.data
        this.userInfo = {
          id,
          username,
          email,
          avatar,
          roles,
          is_superuser,
          is_active,
          portal,
          role_names,
          security_setup_only,
          totp_recovery_only,
          must_change_password,
          acceptance_mode,
        }
        return res.data
      } catch (error) {
        return error
      }
    },
    async logout() {
      const { resetTags } = useTagsStore()
      const { resetPermission } = usePermissionStore()
      removeToken()
      resetTags()
      resetPermission()
      resetRouter()
      this.$reset()
      toLogin()
    },
    setUserInfo(userInfo = {}) {
      this.userInfo = { ...this.userInfo, ...userInfo }
    },
  },
})
