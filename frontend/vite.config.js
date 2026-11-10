import fs from 'node:fs'
import process from 'node:process'
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Windows Smart App Control can block Tailwind's native scanner. Its WebAssembly
// fallback then finds no source files on Windows and generates no utilities, so
// this hands Tailwind the class names from src/ directly. Safe to remove on
// machines where the native scanner loads.
function tailwindInlineSources() {
  const srcDir = path.join(import.meta.dirname, 'src')

  return {
    name: 'tailwind-inline-sources',
    enforce: 'pre',
    transform(code, id) {
      if (!id.split('?')[0].endsWith('/src/index.css')) return null

      const candidates = new Set()
      for (const file of fs.readdirSync(srcDir, { recursive: true })) {
        if (!/\.jsx?$/.test(file)) continue
        const source = fs.readFileSync(path.join(srcDir, file), 'utf8')
        for (const token of source.split(/[\s"'`]+/)) {
          if (token && !/[{}\\;<>]/.test(token)) candidates.add(token)
        }
      }

      const sources = [...candidates].map((candidate) => `@source inline("${candidate}");`)
      return `${code}\n${sources.join('\n')}\n`
    },
  }
}

export default defineConfig({
  plugins: [
    react(),
    tailwindInlineSources(),
    tailwindcss(),
  ],
  server: {
    // Forward API calls to Django so the browser sees one origin (no CORS setup needed).
    proxy: {
      '/api': process.env.VITE_PROXY_TARGET || 'http://localhost:8000',
    },
  },
})
