<template>
  <div class="container-layout">
    <SideBar v-if="isAuthenticated" />
    <main class="content-wrapper">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
const isAuthenticated: boolean = useAuthHydration()
</script>

<style scoped>
.container-layout {
  max-width: 100vw;
  max-height: 100vh;
  display: flex;
  flex-direction: row;

  padding: 5px;
  gap: 10px;

  box-sizing: border-box;
  overflow: hidden;
}

.content-wrapper {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
}
</style>
