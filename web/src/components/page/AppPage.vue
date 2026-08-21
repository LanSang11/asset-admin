<template>
  <transition name="fade-slide" mode="out-in" appear>
    <section class="app-page cus-scroll-y wh-full flex-col">
      <slot />
      <AppFooter v-if="showFooter" mt-15 />
      <n-back-top :bottom="20" />
    </section>
  </transition>
</template>

<script setup>
defineProps({
  showFooter: {
    type: Boolean,
    default: false,
  },
})
</script>
