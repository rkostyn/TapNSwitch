import pluginVue from 'eslint-plugin-vue'
import { defineConfigWithVueTs, vueTsConfigs } from '@vue/eslint-config-typescript'

// Standard Vue 3 + TypeScript presets (as scaffolded by create-vue), no formatting rules.
export default defineConfigWithVueTs(
  {
    name: 'app/files-to-lint',
    files: ['**/*.{ts,mts,tsx,vue}'],
  },
  {
    name: 'app/files-to-ignore',
    ignores: ['**/dist/**', '**/coverage/**', 'public/**'],
  },
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
)
