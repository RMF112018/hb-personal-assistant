import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, mergeConfig } from 'vite'

import base from './vite.config'

const here = path.dirname(fileURLToPath(import.meta.url))

export default mergeConfig(
  base,
  defineConfig({
    server: {
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:8002',
          changeOrigin: true,
          timeout: 300_000,
          proxyTimeout: 300_000,
        },
      },
    },
    root: path.resolve(here),
  }),
)
