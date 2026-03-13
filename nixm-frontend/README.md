# Mantine Vite Template

A modern React application built with Mantine UI components, Vite, and TypeScript, managed with Bun.

## Features

This template comes with the following features:

- [PostCSS](https://postcss.org/) with [mantine-postcss-preset](https://mantine.dev/styles/postcss-preset)
- [TypeScript](https://www.typescriptlang.org/)
- [Storybook](https://storybook.js.org/)
- [Vitest](https://vitest.dev/) setup with [React Testing Library](https://testing-library.com/docs/react-testing-library/intro)
- ESLint setup with [eslint-config-mantine](https://github.com/mantinedev/eslint-config-mantine)

## Prerequisites

- [Bun](https://bun.sh/) installed on your system

## Getting Started

### Installation

Install all dependencies:

```bash
bun install
```

### Development

Start the development server:

```bash
bun run dev
```

The app will be available at `http://localhost:5173`

## Scripts

### Development & Build

- `bun run dev` – Start development server with hot reload
- `bun run build` – Build production version of the app to `dist/` folder
- `bun run preview` – Locally preview the production build

### Testing

- `bun run test` – Run all tests once
- `bun run test:watch` – Run tests in watch mode (re-runs on file changes)
- `bun run test:ui` – Run tests with Vitest UI interface
- `bun run typecheck` – Check TypeScript types without emitting files

### Code Quality

- `bun run lint` – Run ESLint and Stylelint
- `bun run lint:fix` – Auto-fix ESLint and Stylelint issues
- `bun run format` – Format all files with Prettier
- `bun run format:check` – Check if files are formatted correctly
- `bun run validate` – Run full validation (typecheck + format + lint + test + build)

### Storybook

- `bun run storybook` – Start Storybook dev server at `http://localhost:6006`
- `bun run storybook:build` – Build production Storybook bundle to `storybook-static/`

## Testing the Production Build

To test how your app will behave in production:

```bash
# Build the production version
bun run build

# Preview the built app locally
bun run preview
```

The preview server will start at `http://localhost:4173` (or another available port).

### Alternative: Using a Static Server

You can also serve the `dist/` folder with any static file server:

```bash
# Build first
bun run build

# Serve the dist folder
cd dist
bunx serve
```

## Project Structure

```
vite-template/
├── src/                  # Application source code
│   ├── components/       # React components
│   ├── pages/           # Page components
│   └── assets/          # Images, fonts, etc.
├── public/              # Static files served directly
├── test-utils/          # Testing utilities and setup
├── .storybook/          # Storybook configuration
└── dist/                # Production build output (generated)
```

## Deployment

After running `bun run build`, the `dist/` folder contains your production-ready app. Deploy this folder to any static hosting service:

- **Vercel**: `bunx vercel deploy`
- **Netlify**: `bunx netlify deploy --prod --dir=dist`
- **GitHub Pages**: Push `dist/` folder contents to `gh-pages` branch

## Learn More

- [Mantine Documentation](https://mantine.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Bun Documentation](https://bun.sh/docs)
- [React Documentation](https://react.dev/)