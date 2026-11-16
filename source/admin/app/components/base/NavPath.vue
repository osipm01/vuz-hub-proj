
<style lang="css">
</style>

<template>

    <span>{{ formattedPath }}</span>

</template>

<script setup lang="ts">
    
const route = useRoute()

// Переменная также очищает начальный слэш, чтобы не получилось "->about" вместо "about"
const formattedPath = computed(() => {
  return route.path.replace(/^\//, '').replace(/\//g, '=>')
})
</script>