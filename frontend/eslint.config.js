import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // эффект, записанный стрелкой без фигурных скобок, возвращает значение выражения,
      // и React вызывает его как функцию очистки (так scrollIntoView обрушивал чат и экзамен)
      'no-restricted-syntax': ['error', {
        selector: "CallExpression[callee.name=/^use(Layout)?Effect$/] > ArrowFunctionExpression[expression=true]:not([body.type='ArrowFunctionExpression']):not([body.type='FunctionExpression'])",
        message: 'Тело эффекта пишите в фигурных скобках: эффект может вернуть только функцию очистки.',
      }],
    },
  },
  {
    // сгенерированные компоненты shadcn/ui экспортируют варианты стилей вместе с компонентами
    files: ['src/components/ui/**/*.tsx'],
    rules: { 'react-refresh/only-export-components': 'off' },
  },
])
