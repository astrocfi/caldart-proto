import js from '@eslint/js';
import jsdoc from 'eslint-plugin-jsdoc';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'coverage', 'playwright-report', 'test-results'] },
  {
    extends: [
      js.configs.recommended,
      ...tseslint.configs.recommendedTypeChecked,
      jsxA11y.flatConfigs.recommended,
    ],
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.node },
      // `projectService` hands each linted file to the TypeScript program that
      // already owns it, so a file added to `tsconfig.json` is type-checked by
      // ESLint without a second list to keep in step.
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      jsdoc,
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
      '@typescript-eslint/explicit-module-boundary-types': 'error',
      'jsdoc/require-jsdoc': [
        'error',
        {
          publicOnly: true,
          require: {
            FunctionDeclaration: true,
            ArrowFunctionExpression: true,
            FunctionExpression: true,
            ClassDeclaration: true,
          },
        },
      ],
      'jsdoc/no-types': 'error',
      // `base.css` strips the markers from both `ul[role='list']` and
      // `ol[role='list']`, and Safari's VoiceOver stops announcing a list once
      // its markers are gone.  The attribute is what keeps the semantics, so it
      // is not redundant here.
      'jsx-a11y/no-redundant-roles': ['error', { ul: ['list'], ol: ['list'] }],
    },
  },
);
