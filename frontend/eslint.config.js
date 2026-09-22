import js from '@eslint/js';
import jsdoc from 'eslint-plugin-jsdoc';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

// The component barrel is gone: every import names the file it defines.
const barrelPaths = [
  {
    name: '@/portal/components',
    message: 'Import the component file directly, not the barrel.',
  },
  {
    name: './components',
    message: 'Import the component file directly, not the barrel.',
  },
  {
    name: '../components',
    message: 'Import the component file directly, not the barrel.',
  },
];

export default tseslint.config(
  {
    ignores: [
      'dist',
      'node_modules',
      'coverage',
      'playwright-report',
      'test-results',
      // Generated from the backend's OpenAPI description by `npm run schema`.
      'src/portal/api/schema.d.ts',
    ],
  },
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
      react,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      jsdoc,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      // Every local event handler is named `handle*`; a prop that hands one
      // down to a child is named `on*`. Keeps the two roles visually distinct
      // at a glance across the whole portal.
      'react/jsx-handler-names': [
        'error',
        { eventHandlerPrefix: 'handle', checkLocalVariables: true },
      ],
      // Outside `src/portal/features/`, a relative import may reach its own
      // parent (`../components/Button` from `src/portal/routes/`) but never
      // climb further: two levels up is another part of the tree, and the
      // `@/` alias names it plainly.
      'no-restricted-imports': [
        'error',
        {
          paths: barrelPaths,
          patterns: [
            {
              group: ['../../*', '../../**'],
              message: "Use the '@/' alias rather than climbing out with '../..'.",
            },
          ],
        },
      ],
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
  {
    // A feature directory is the unit of relative addressing: inside
    // `src/portal/features/<feature>/` a relative import must stay in the
    // feature, so any specifier starting with `../` is refused -- one level up
    // is already a sibling feature. Every feature is a flat directory; a
    // feature that grows a subdirectory adds a `files` entry here exempting
    // `src/portal/features/<feature>/<subdir>/**` so its files can still reach
    // their own feature root with `../`.
    files: ['src/portal/features/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          paths: barrelPaths,
          patterns: [
            {
              group: ['../*', '../**'],
              message:
                "Use the '@/' alias to import outside the feature; relative paths stay inside it.",
            },
          ],
        },
      ],
    },
  },
);
