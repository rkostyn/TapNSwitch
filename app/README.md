# TapNSwitch APP Frontend.

This template should help get you started developing with Vue 3 in Vite.

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Type-Check, Compile and Minify for Production

```sh
npm run build
```

### Unit Tests and Lint

```sh
npm run test   # Vitest: scoring rules, match list order, venue store, event type rules
npm run lint   # ESLint (eslint-plugin-vue + typescript-eslint)
```

## Tournaments

A tournament is a type of event, not a separate app or deployment: everyday groups and
tournaments run side by side. Staff pick **Standard group** or **Tournament** when creating an
event, and can switch an event's type (for example a Checkfront booking that is a tournament)
from its detail screen until matches are generated. Tournament events default to Swiss, and
the API deals their generated matches onto the group's lanes; each match in the list shows its
lane whenever it has one. The type-dependent choices live in `src/eventType.ts`.

### Local dev API

`npm run dev` proxies API calls to `API_TARGET` (default http://localhost:8001), read from the
shell or `.env.development`.
