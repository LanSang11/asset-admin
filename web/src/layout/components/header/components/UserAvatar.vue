<template>
  <n-dropdown :options="options" @select="handleSelect">
    <button class="user-avatar" type="button" aria-label="打开用户菜单">
      <img class="user-avatar__img" :src="displayAvatar" alt="头像" draggable="false" />
      <span class="user-avatar__name">{{ userStore.name }}</span>
    </button>
  </n-dropdown>
</template>

<script setup>
import { computed } from 'vue'
import { useUserStore } from '@/store'
import { renderIcon } from '@/utils'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const props = defineProps({
  profilePath: {
    type: String,
    default: '/profile',
  },
})

// 无个人头像时用原创默认头像，不用系统标识
const defaultAvatar = `${import.meta.env.BASE_URL}resource/default-avatar.jpg`
const displayAvatar = computed(() => userStore.avatar || defaultAvatar)

const options = [
  {
    label: t('header.label_profile'),
    key: 'profile',
    icon: renderIcon('mdi:account-arrow-right-outline', { size: '14px' }),
  },
  {
    label: t('header.label_logout'),
    key: 'logout',
    icon: renderIcon('mdi:exit-to-app', { size: '14px' }),
  },
]

function handleSelect(key) {
  if (key === 'profile') {
    router.push(props.profilePath)
  } else if (key === 'logout') {
    $dialog.confirm({
      title: t('header.label_logout_dialog_title'),
      type: 'warning',
      content: t('header.text_logout_confirm'),
      confirm() {
        userStore.logout()
        $message.success(t('header.text_logout_success'))
      },
    })
  }
}
</script>

<style scoped>
.user-avatar__img {
  width: 35px;
  height: 35px;
  min-width: 35px;
  min-height: 35px;
  margin-right: 10px;
  border-radius: 50%;
  object-fit: cover;
  object-position: center;
  display: block;
  box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.06);
  background: #fff;
}

.user-avatar__name {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-avatar {
  display: inline-flex;
  align-items: center;
  min-width: 40px;
  min-height: 40px;
  padding: 0;
  border: 0;
  border-radius: 8px;
  color: inherit;
  background: transparent;
  font: inherit;
  line-height: 1;
  cursor: pointer;
}

.user-avatar:hover,
.user-avatar:focus-visible {
  background: var(--topbar-action-hover, rgba(148, 163, 184, 0.18));
  outline: none;
}

.user-avatar:focus-visible {
  box-shadow: 0 0 0 2px var(--shell-accent);
}

@media (max-width: 767.98px) {
  .user-avatar__img {
    width: 34px;
    height: 34px;
    min-width: 34px;
    min-height: 34px;
    margin-right: 0;
  }

  .user-avatar__name {
    display: none;
  }
}
</style>
