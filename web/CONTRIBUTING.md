# Contributing Guide

## Development Setup

```bash
# Clone and install
git clone <repo-url>
cd web
pnpm install

# Canonical local stack
cd ../backend
./scripts/run-compose-stack.sh

cd ../web
pnpm start

# Secondary surfaces
pnpm run dev:all       # core profile only
pnpm run dev:remotes   # minimal remotes
```

## Code Quality

- **Formatting**: Prettier (auto-enforced via pre-commit hook)
- **Linting**: ESLint with TypeScript + custom plugins
- **Style linting**: Stylelint for CSS
- **Type checking**: `pnpm typecheck`

## Commit Convention

We use conventional commits:
- `feat(scope):` New feature
- `fix(scope):` Bug fix
- `docs(scope):` Documentation
- `refactor(scope):` Code refactoring
- `test(scope):` Test additions/changes
- `chore(scope):` Build/tooling changes

## Pull Request Process

1. Create a feature branch from `main`
2. Make changes with tests
3. Ensure all checks pass: `pnpm test && pnpm typecheck && pnpm format:check`
4. Submit PR with description of changes
5. Address review feedback
6. Merge after approval

## Package Structure

```
packages/
├── design-system/     Core UI primitives + tokens
├── blocks/            Pre-built page templates
├── x-data-grid/       Enterprise data grid recipes
├── x-charts/          Chart components (AG Charts)
├── x-scheduler/       Calendar/scheduler
├── x-kanban/          Kanban board
├── x-editor/          Rich text editor
├── x-form-builder/    JSON schema form renderer
├── create-app/        CLI scaffold generator
└── i18n-dicts/        Translation dictionaries

apps/
├── mfe-shell/         Host application
├── docs/              Documentation portal (Nextra)
└── mfe-*/             Micro-frontend apps
```

## Testing

- Unit tests: `pnpm test`
- X-suite tests: `pnpm test:x-suite`
- Design system: `pnpm --filter @mfe/design-system test`
- Type check: `pnpm typecheck:x-suite`
