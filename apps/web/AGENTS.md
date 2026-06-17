# Frontend Template

Standalone Vike SSR template. Use pnpm, not npm or yarn.

## Structure

- `pages/` - Vike plus files and routes.
- `pages/+Layout.tsx` - app shell, owns `<main>`.
- `server/hono.ts` - Hono server mounted by Vike.
- `components/ui/` - shadcn primitives owned by this repo.
- `components/Shell.tsx` - neutral app chrome.
- `components/ExampleCard.*` - sample spec-first component.
- `lib/domain/` - Zod schemas and domain types.

## Commands

```bash
pnpm dev
pnpm build
pnpm typecheck
pnpm lint
pnpm lint:fix
pnpm vitest run
pnpm vitest run --project=unit
pnpm vitest run --project=storybook
pnpm storybook
```

## Conventions

- Vike routes live in `pages/`; dynamic segments use `@name`.
- Layout owns the only `<main>`.
- Tailwind v4 styles and shadcn theme live in `pages/tailwind.css`.
- shadcn primitives in `components/ui/` are project-owned code.
- Use `@/` imports for project files.
- Trust-boundary data uses Zod.
- Client server state uses TanStack Query; local UI state can use React state or Zustand.
- Components should be mobile-first and width-safe.

## Workflow

Write spec, red tests/stories, implementation, then green checks. Keep feature docs colocated. Do not add implementation details to specs unless product intent changed.

## Spec-First TDD

Non-trivial features use the quadruplet:

- `<feature>.spec.md`
- code
- stories
- tests

Specs describe what, why, and acceptance criteria. Tests carry technical contracts.

Use Storybook `play` tests when DOM behavior matters. Use sibling `*.test.ts` for pure logic, schemas, adapters, stores, and server handlers.

## Testing

- `pnpm vitest run --project=unit` for pure logic.
- `pnpm vitest run --project=storybook` for story `play` tests.
- `pnpm typecheck` before finishing.
- `pnpm build` for production validation.

## UI

Use existing primitives before adding dependencies. Use lucide icons for icon buttons. Keep pages usable on mobile first; cap width on desktop with `max-w-*`.

## Gotchas

- Storybook test imports come from `storybook/test`.
- Portal content is queried from `document.body`, not `canvasElement`.
- Tailwind v4 gradient utilities are `bg-linear-to-*`.
- Biome is the linter/formatter.
- Vike hook path is `vike-react/usePageContext`.
