<template>
  <div class="input-field-group">
    <label v-if="label" :for="fieldId" class="field-label">{{ label }}</label>
    <slot />
    <p v-if="hint" class="field-hint">{{ hint }}</p>
    <p v-if="error" class="field-error">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed, useId } from 'vue'

const props = defineProps<{
  label?: string
  hint?: string
  error?: string
  id?: string
}>()

const generatedId = useId()
const fieldId = computed(() => props.id || `field-${generatedId}`)
</script>