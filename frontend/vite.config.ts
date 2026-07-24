import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5222,
    // On Windows, watching src-tauri/target while cargo writes .o files
    // throws EBUSY and kills the Vite beforeDevCommand mid-compile.
    watch: {
      ignored: ['**/src-tauri/target/**'],
    },
  },
})
