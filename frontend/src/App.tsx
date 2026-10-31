import { useEffect, useRef, useState } from 'react'
import { createFlightPreview } from './api/flightPreviews'
import type { FlightPreview } from './api/flightPreviews'
import CsvFilePicker from './components/CsvFilePicker'
import FlightChart from './components/charts/FlightChart'
import FlightRoute3D from './components/charts/FlightRoute3D'
import './App.css'

type PreviewState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; preview: FlightPreview }
  | { status: 'error'; message: string }

function App() {
  const [file, setFile] = useState<File | null>(null)
  const [previewState, setPreviewState] = useState<PreviewState>({ status: 'idle' })
  const activeRequest = useRef<AbortController | null>(null)

  useEffect(() => () => {
    activeRequest.current?.abort()
    activeRequest.current = null
  }, [])

  const handleFileChange = (nextFile: File | null) => {
    // A response for a replaced/removed file must never become its new preview.
    activeRequest.current?.abort()
    activeRequest.current = null
    setFile(nextFile)
    setPreviewState({ status: 'idle' })
  }

  const handleGeneratePreview = async () => {
    if (!file || activeRequest.current) return
    const controller = new AbortController()
    activeRequest.current = controller
    setPreviewState({ status: 'loading' })

    try {
      const preview = await createFlightPreview(file, controller.signal)
      if (activeRequest.current === controller) {
        setPreviewState({ status: 'success', preview })
      }
    } catch (error) {
      if (activeRequest.current === controller && !controller.signal.aborted) {
        setPreviewState({
          status: 'error',
          message: error instanceof Error ? error.message : 'Could not generate the preview. Try again.',
        })
      }
    } finally {
      if (activeRequest.current === controller) activeRequest.current = null
    }
  }

  const preview = previewState.status === 'success' ? previewState.preview : null

  return (
    <main className="app">
      <div className="dashboard">
        <header className="dashboard-header">
          <div className="brand">
            <svg className="brand-mark" viewBox="0 0 40 40" aria-hidden="true">
              <path d="M5 25 18 20 25 7l4-2-3 15 8 7-1 3-11-5-7 7-3-1 4-8Z" fill="currentColor" />
            </svg>
            <span>Electric Aircraft<span className="brand-subtitle">SIMULATION WORKSPACE</span></span>
          </div>
          <span className="workspace-tab">Flight preview</span>
          <span className="mode-badge"><span />Profile preview</span>
        </header>

        <div className="page-heading">
          <div>
            <p className="eyebrow">Mission analysis / CSV workspace</p>
            <h1 id="page-title">Flight profile preview</h1>
            <p className="description">Turn your flight log into a mission you can explore.</p>
          </div>
          <p className="workflow-label"><span>01</span> Import & inspect</p>
        </div>

        <div className="workspace-grid">
          <section className="panel mission-panel" aria-labelledby="mission-title">
            <div className="mission-toolbar">
              <div className="panel-heading">
                <div><p className="panel-kicker">Source data</p><h2 id="mission-title">Mission input</h2></div>
              </div>
              <CsvFilePicker file={file} onFileChange={handleFileChange} compact />
              <button
                className="generate-preview"
                type="button"
                disabled={!file || previewState.status === 'loading'}
                onClick={handleGeneratePreview}
              >
                {previewState.status === 'loading' ? 'Generating preview…' : 'Generate preview'}
                <span aria-hidden="true">↗</span>
              </button>
            </div>
            <div className="mission-feedback">
              <div aria-live="polite" aria-atomic="true">
                {previewState.status === 'loading' && (
                  <p className="preview-loading" role="status">Checking the flight CSV and generating waypoints…</p>
                )}
                {preview && <p className="preview-confirmation">Preview generated.</p>}
              </div>
              <details className="input-help">
                <summary>CSV format &amp; privacy</summary>
                <p className="privacy-note">Your CSV is sent to the local API only when you generate a preview. Uploads are not retained.</p>
                <p className="input-requirements">Required channels: time(ms) · LAT · LNG · PRESSURE_ALT</p>
              </details>
            </div>
            {previewState.status === 'error' && (
              <div className="preview-error" role="alert">
                <h3>Preview could not be generated</h3>
                <p>{previewState.message}</p>
                <p>Check the file or local API, then choose Generate preview to retry.</p>
              </div>
            )}
          </section>

          <section className="panel route-panel" aria-labelledby="route-title">
            <div className="panel-heading">
              <div><p className="panel-kicker">Flight geometry</p><h2 id="route-title">Flight route</h2></div>
              <span className={`panel-badge ${preview ? 'is-ready' : ''}`}>
                {preview ? 'CSV profile' : 'Awaiting preview'}
              </span>
            </div>
            {preview ? <FlightChart kind="route" preview={preview} /> : (
              <div className="chart-empty route-empty">
                <div className="empty-crosshair" aria-hidden="true"><span>+</span></div>
                <h3>Your flight path starts here</h3>
                <p>Select a flight CSV and generate a preview<br />to inspect its route.</p>
              </div>
            )}
            <div className="route-footer">
              <span><i className="legend-dot start-dot" />Start <i className="legend-dot end-dot" />End</span>
              <span>Local east / north · meters · equal scale</span>
            </div>
          </section>

          <section className="panel altitude-panel" aria-labelledby="altitude-title">
            <div className="panel-heading">
              <div><p className="panel-kicker">Vertical profile</p><h2 id="altitude-title">Altitude profile</h2></div>
              <span className="panel-badge">Relative pressure altitude (m)</span>
            </div>
            {preview ? <FlightChart kind="altitude" preview={preview} /> : (
              <div className="chart-empty altitude-empty">
                <span className="empty-profile" aria-hidden="true">⌁</span>
                <p>Your altitude profile will appear after preview generation.</p>
              </div>
            )}
            <p className="chart-caption">Relative to the first CSV pressure altitude sample.{preview && ' Drag the time slider to zoom.'}</p>
          </section>

          <section className="panel spatial-panel" aria-labelledby="spatial-title">
            <div className="panel-heading">
              <div><p className="panel-kicker">Spatial profile</p><h2 id="spatial-title">3D flight route</h2></div>
              <span className="panel-badge">3D view</span>
            </div>
            {preview ? <FlightRoute3D preview={preview} /> : (
              <div className="chart-empty spatial-empty">
                <div className="empty-crosshair spatial-crosshair" aria-hidden="true"><span>⌁</span></div>
                <h3>Explore the route in 3D</h3>
                <p>Generate a preview to see<br />position and altitude together.</p>
              </div>
            )}
            <p className="chart-caption">East / North / Relative pressure altitude (m). Altitude is relative to the first CSV sample.</p>
          </section>
        </div>

        <section className="panel preview-summary" aria-labelledby="preview-title">
          <div className="panel-heading">
            <div><p className="panel-kicker">Mission overview</p><h2 id="preview-title">{preview ? 'Preview ready' : 'Preview summary'}</h2></div>
            <span className="step-number">02</span>
          </div>
          <dl className="preview-metrics">
            <div><dt>CSV samples</dt><dd>{preview ? preview.sample_count.toLocaleString() : '—'}</dd></div>
            <div><dt>Waypoints</dt><dd>{preview ? preview.waypoint_count.toLocaleString() : '—'}</dd></div>
            <div className="duration-metric"><dt>Flight duration</dt><dd>{preview ? `${preview.duration_s.toLocaleString(undefined, { maximumFractionDigits: 3 })} s` : '—'}</dd></div>
          </dl>
          <div className="reference-details">
            <div><span>Waypoint interval</span><strong>{preview ? `${preview.downsample_sec} s` : '1 s default'}</strong></div>
            <div><span>Initial pressure altitude</span><strong>{preview ? `${preview.origin.pressure_altitude_m.toLocaleString(undefined, { maximumFractionDigits: 1 })} m` : '—'}</strong></div>
          </div>
          <p className="simulation-note">CSV profile preview only. Simulation has not run.</p>
        </section>
        <footer className="dashboard-footer"><span>Electric Aircraft Simulator</span><span>CSV <span aria-hidden="true">→</span> Waypoints <span aria-hidden="true">→</span> Profile preview</span></footer>
      </div>
    </main>
  )
}

export default App
