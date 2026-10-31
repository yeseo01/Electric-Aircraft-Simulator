# Electric Aircraft Simulator — Frontend

React + TypeScript + Vite application generated from the official `react-ts`
template. The page now accepts a CSV through drag-and-drop or the native file
chooser and displays the selected filename and size. **Generate preview** sends
the selected CSV to FastAPI and displays the sample count, waypoint count, and
flight duration. A dark dashboard also plots the east/north route and relative
pressure altitude over time, with start/end markers, tooltips, and a time zoom
slider. This implements the preview workflow in
[issue #1](https://github.com/yeseo01/Electric-Aircraft-Simulator/issues/1).

## Prerequisites

Install [Node.js](https://nodejs.org/en/download) 24 or newer, including npm.
Check your terminal with `node --version` and `npm --version`.
The initial scaffold was verified with Node.js 26.8.2 and npm 11.19.1.

The frontend is independent of the Python virtual environment and does not
require the API server for file selection.
Generating a preview requires both servers below.

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

In a second terminal at the repository root, start the API:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

See the root README for Python dependency installation if the virtual environment
has not been prepared. Keep both terminals running during preview generation.
Use **Choose CSV** or drop a file, then click **Generate preview**. Merely choosing
a file does not send it. The button shows a loading state until the API responds.
Errors include the CSV column and physical line number where available; fix the
file or restart the API and click the button again to retry.

The route uses local east/north meters at equal scale, not geographic map tiles.
The altitude plot uses elapsed seconds and pressure altitude relative to the
first CSV sample. Hover or click the plots to inspect coordinates. Drag the
altitude time slider or zoom inside the altitude plot to inspect a time range.
Resizing the panel preserves the route's equal scale. On narrow screens, the
input panel moves above the charts. Empty states and summary dashes remain until
a preview succeeds; there is no fabricated flight data or simulation telemetry.

Vite forwards `/api/*` to `http://127.0.0.1:8000` through `server.proxy` in
`vite.config.ts`. The browser uses a relative URL, so no cross-origin request
configuration is needed for this local workflow. Restart Vite when changing its
proxy configuration. For deployment, configure the host/reverse proxy to route
`/api` to the Python backend; these dev-server settings are not bundled into the
static production assets.

`npm ci` installs the versions recorded in `package-lock.json`. Commit that
lockfile when dependencies change. `node_modules/` and generated `dist/` files
are ignored by Git.

## File selection behavior

- Choose or drop exactly one nonempty `.csv` file, up to 10 MiB.
- Change the selected file or remove it. Cancelling the chooser keeps the selection.
- An invalid replacement clears the old selection and shows an error.
- Selecting a file keeps a browser `File` object in React state. Only **Generate
  preview** transmits it to the local backend, using multipart form data and the
  default 1-second waypoint interval. The application does not retain uploads;
  the framework releases temporary upload files when the request completes.
- Changing/removing the file clears previous results/errors and aborts any
  outstanding browser request. Late responses cannot overwrite the new selection.
  Aborting the browser request does not guarantee that server computation stops.
- No file or result is saved to persistent browser storage. Refreshing clears both.

The extension, size, and count checks provide immediate feedback; they do not
verify that the contents are a valid flight log. The backend validates CSV rows
and columns after submission; the client checks the returned JSON contract.
Private flight logs remain outside the repository; tests create synthetic files
in memory.

## Test and build

```bash
npm test
npm run build
```

Vitest and React Testing Library exercise selection, replacement, removal,
drag-and-drop, validation boundaries, keyboard access, multipart requests, errors,
retry, loading states, cancellation, late-response handling, chart coordinate
mapping, equal scale, stationary routes, resize, and chart cleanup. Use `npm run test:watch`
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
| `src/App.tsx` | Selected file, request lifecycle, loading/error/summary UI |
| `src/api/flightPreviews.ts` | API types, FormData/fetch, response checks, error messages |
| `src/api/flightPreviews.test.ts` | Multipart and response contract tests |
| `src/App.test.tsx` | Submit, retry, loading, and stale-response interaction tests |
| `src/components/charts/FlightChart.tsx` | ECharts registration, React lifecycle, ResizeObserver, SVG rendering |
| `src/components/charts/chartOptions.ts` | Route/altitude options, units, equal scale, endpoints, and time zoom |
| `src/components/charts/*.test.*` | Coordinate semantics and chart lifecycle tests |
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

For a step-by-step Korean explanation of this increment, see
[React → FastAPI learning notes](../docs/learning/react-fastapi-preview.md).
For the dashboard and charts increment, see
[dashboard learning notes](../docs/learning/flight-dashboard-charts.md).
