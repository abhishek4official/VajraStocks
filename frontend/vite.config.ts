import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { readFileSync } from 'fs'
import { resolve } from 'path'

const pkg = JSON.parse(readFileSync(resolve(__dirname, 'package.json'), 'utf-8'))

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    // Bakes the version from package.json into the bundle at build time.
    // Use as: import.meta.env.VITE_APP_VERSION in any component.
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(pkg.version),
  },
})
