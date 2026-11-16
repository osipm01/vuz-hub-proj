import { defineConfig } from 'vitest/config'
import tsconfigPaths from 'vite-tsconfig-paths'
import { defineNuxtConfig } from 'nuxt/config'

export default defineNuxtConfig({
  plugins: [
    tsconfigPaths() // <- Это заставит Vitest понять, что такое "~/"
  ],
  test: {
    environment: 'nuxt',
    // Если тесты написаны в .vue или .ts файлах, укажите это:
    include: ['**/*.{test,spec}.{ts,js,vue}']
  }
})
