# Electric Aircraft Simulator — Frontend

React + TypeScript + Vite scaffold generated from the official `react-ts`
template. This increment renders the initial page; CSV upload, API calls, and
charts are subsequent steps in [issue #1](https://github.com/yeseo01/Electric-Aircraft-Simulator/issues/1).

## Prerequisites

Install [Node.js](https://nodejs.org/en/download) 24 or newer, including npm.
Check your terminal with `node --version` and `npm --version`.
The initial scaffold was verified with Node.js 26.8.2 and npm 11.19.1.

The frontend is independent of the Python virtual environment and does not
require the API server to render this initial page.

## Install and run

From the repository root:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open the printed Local URL, normally `http://127.0.0.1:5173`.
Change `src/App.tsx` and save to see Vite update the page.
Stop the server with `Ctrl+C`.

`npm ci` installs the versions recorded in `package-lock.json`. Commit that
lockfile when dependencies change. `node_modules/` and generated `dist/` files
are ignored by Git.

## Build

```bash
npm run build
```

This runs TypeScript checking and creates a production build in `dist/`.
Use `npm run preview` to serve that build locally after it succeeds.
The template also includes Oxlint configuration and an `npm run lint` command
for future lint checks.

## Read the code in this order

| File | Role |
| --- | --- |
| `index.html` | HTML entry point; contains the root element and loads `main.tsx` |
| `src/main.tsx` | Mounts React's `App` component inside the root element |
| `src/App.tsx` | Initial page component |
| `src/index.css` | Global styles |
| `src/App.css` | Page styles |
| `package.json` | Dependencies, Node requirement, and npm commands |
| `package-lock.json` | Exact resolved dependency versions for repeatable installs |
| `vite.config.ts` | Vite configuration and React plugin |
| `tsconfig*.json` | TypeScript settings for app and tooling code |

See the [Vite guide](https://vite.dev/guide/) and
[React setup guide](https://react.dev/learn/build-a-react-app-from-scratch)
for the original setup workflow.
