import js from '@eslint/js';
import jsdoc from 'eslint-plugin-jsdoc';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage', 'playwright-report', 'test-results'] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // The design system deliberately co-locates a component with the pure
      // helper that computes its input (`membershipTone` beside `StatusChip`,
      // `formatCents` beside `Money`), which this rule cannot express.  Losing
      // fast refresh on those files is a fair trade for keeping them together.
      'react-refresh/only-export-components': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      '@typescript-eslint/consistent-type-imports': [
        'error',
        { prefer: 'type-imports', fixStyle: 'separate-type-imports' },
      ],
    },
  },
  {
    files: ['**/*.test.{ts,tsx}', 'src/test/**/*.{ts,tsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  {
    // Grows one directory at a time as the return-type and JSDoc sweeps
    // (#44, #45) cover more of the tree; the last sweep widens this to
    // `**/*.{ts,tsx}` and folds the two rules into the block above.
    files: [
      'src/portal/components/**/*.{ts,tsx}',
      'src/portal/api/**/*.{ts,tsx}',
      'src/portal/auth/**/*.{ts,tsx}',
      'src/portal/routes/**/*.{ts,tsx}',
      'src/portal/layout/**/*.{ts,tsx}',
      'src/portal/App.tsx',
      'src/portal/choices.ts',
      'src/portal/nav.ts',
      'src/site/**/*.{ts,tsx}',
      'src/test/**/*.{ts,tsx}',
      'e2e/**/*.{ts,tsx}',
      'src/portal/features/admin-aircraft/**/*.{ts,tsx}',
      'src/portal/features/admin-members/**/*.{ts,tsx}',
      'src/portal/features/admin-payments/**/*.{ts,tsx}',
      'src/portal/features/admin-users/**/*.{ts,tsx}',
      'src/portal/features/aircraft/**/*.{ts,tsx}',
      'src/portal/features/auth/**/*.{ts,tsx}',
      'src/portal/features/checkout/**/*.{ts,tsx}',
      'src/portal/features/dashboard/**/*.{ts,tsx}',
    ],
    plugins: {
      jsdoc,
    },
    rules: {
      '@typescript-eslint/explicit-module-boundary-types': 'error',
      'jsdoc/require-jsdoc': [
        'error',
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            ArrowFunctionExpression: true,
            FunctionExpression: true,
          },
        },
      ],
      'jsdoc/no-types': 'error',
    },
  },
);
