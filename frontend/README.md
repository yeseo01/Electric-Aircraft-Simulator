# Electric Aircraft Simulator — Frontend

React + TypeScript + Vite application generated from the official `react-ts`
template. The page now accepts a CSV through drag-and-drop or the native file
chooser and displays the selected filename and size. API upload and charts are
subsequent steps in [issue #1](https://github.com/yeseo01/Electric-Aircraft-Simulator/issues/1).

## Prerequisites

Install [Node.js](https://nodejs.org/en/download) 24 or newer, including npm.
Check your terminal with `node --version` and `npm --version`.
The initial scaffold was verified with Node.js 26.8.2 and npm 11.19.1.

The frontend is independent of the Python virtual environment and does not
require the API server for file selection.

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

## File selection behavior

- Choose or drop exactly one nonempty `.csv` file, up to 10 MiB.
- Change the selected file or remove it. Cancelling the chooser keeps the selection.
- An invalid replacement clears the old selection and shows an error.
- The file remains a browser `File` object in React state. This step makes no API
  request, reads no CSV contents, and saves no file to browser or server storage.
  Refreshing the page clears the selection.

The extension, size, and count checks provide immediate feedback; they do not
verify that the contents are a valid flight log. The existing backend will
validate CSV rows and columns when the API is connected in the next increment.
Private flight logs remain outside the repository; tests create synthetic files
in memory.

## Test and build

```bash
npm test
npm run build
```

Vitest and React Testing Library exercise selection, replacement, removal,
drag-and-drop, validation boundaries, and keyboard access. Use `npm run test:watch`
to rerun tests as you edit.

The build runs TypeScript checking and creates production assets in `dist/`.
Use `npm run preview` to serve that build locally after it succeeds.
The template also includes Oxlint configuration and an `npm run lint` command
for future lint checks.

## Read the code in this order

| File | Role |
| --- | --- |
| `index.html` | HTML entry point; contains the root element and loads `main.tsx` |
| `src/main.tsx` | Mounts React's `App` component inside the root element |
| `src/App.tsx` | Page component; owns the selected `File` in React state |
| `src/components/CsvFilePicker.tsx` | Native input, drag events, metadata checks, and selection feedback |
| `src/components/CsvFilePicker.css` | Drop area, selected file, and error styles |
| `src/components/CsvFilePicker.test.tsx` | User interaction tests with synthetic files |
| `src/test/setup.ts` | DOM assertions and test cleanup |
| `src/index.css` | Global styles |
| `src/App.css` | Page styles |
| `package.json` | Dependencies, Node requirement, and npm commands |
| `package-lock.json` | Exact resolved dependency versions for repeatable installs |
| `vite.config.ts` | Vite, React plugin, and Vitest configuration |
| `tsconfig*.json` | TypeScript settings for app and tooling code |

See the [Vite guide](https://vite.dev/guide/) and
[React setup guide](https://react.dev/learn/build-a-react-app-from-scratch)
for the original setup workflow.
