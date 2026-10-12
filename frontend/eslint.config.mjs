import { defineConfig, globalIgnores } from 'eslint/config'
import nextVitals from 'eslint-config-next/core-web-vitals'
import nextTs from 'eslint-config-next/typescript'

export default defineConfig([
  ...nextVitals,
  ...nextTs,
  globalIgnores(['.next/**', 'out/**', 'build/**', 'coverage/**', 'next-env.d.ts']),

  // Baseline of findings that existed when CI was introduced: reported as
  // warnings in these files only, errors everywhere else. Remove entries as
  // the underlying code is cleaned up.
  {
    files: [
      'app/(dashboard)/controls/ControlDrawer.tsx',
      'app/(dashboard)/layout.tsx',
      'app/login/page.tsx',
      'components/ThemeProvider.tsx',
    ],
    rules: { 'react-hooks/set-state-in-effect': 'warn' },
  },
  {
    files: ['app/(dashboard)/vendors/page.tsx'],
    rules: { 'react-hooks/immutability': 'warn' },
  },
  {
    files: ['app/reset-password/page.tsx'],
    rules: { 'react/no-unescaped-entities': 'warn' },
  },
  {
    files: ['app/signup/page.tsx'],
    rules: { '@typescript-eslint/no-explicit-any': 'warn' },
  },
  {
    files: ['components/Card.tsx'],
    rules: { '@typescript-eslint/no-empty-object-type': 'warn' },
  },
])
