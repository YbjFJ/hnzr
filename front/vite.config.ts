import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    },
  },
  server: {
    proxy: {
      // 1. 将这里改为 '/api'，这样能捕获所有 /api 开头的请求
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        // 2. 关键点：如果你的前端代码里只写了 /api/user/login
        // 但后端需要 /api/v1/user/login，则需要在这里手动补上 /v1
        rewrite: (path) => path.replace(/^\/api/, '/api/v1'),
        // proxy_buffering 不是 Vite 的 ProxyOptions 合法字段，如需关闭缓冲请在后端服务器配置

      }
    }
  }
})