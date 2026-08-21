<template>
  <div class="app-header-compat">
    <div flex items-center>
      <MenuCollapse />
      <BreadCrumb ml-15 hidden sm:block />
    </div>
    <HeaderActions :profile-path="props.profilePath" />
  </div>
</template>

<script setup>
import BreadCrumb from './components/BreadCrumb.vue'
import MenuCollapse from './components/MenuCollapse.vue'
import HeaderActions from './HeaderActions.vue'

const props = defineProps({
  profilePath: {
    type: String,
    default: '/profile',
  },
})
</script>

<style scoped>
.app-header-compat {
  display: flex;
  align-items: center;
  width: 100%;
  min-width: 0;
}
</style>
