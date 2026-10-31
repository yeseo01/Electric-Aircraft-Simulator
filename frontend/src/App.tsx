import { useEffect, useRef, useState } from 'react'
import { createFlightPreview } from './api/flightPreviews'
import type { FlightPreview } from './api/flightPreviews'
import CsvFilePicker from './components/CsvFilePicker'
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

  return (
    <main className="app">
      <section className="welcome" aria-labelledby="page-title">
        <p className="eyebrow">Electric Aircraft Simulator</p>
        <h1 id="page-title">Flight profile preview</h1>
        <p className="description">Start with your flight log.</p>
        <CsvFilePicker file={file} onFileChange={handleFileChange} />
        <p className="next-step">
          Your CSV is sent to the local API only when you generate a preview.
          Uploads are not retained.
        </p>
        <button
          className="generate-preview"
          type="button"
          disabled={!file || previewState.status === 'loading'}
          onClick={handleGeneratePreview}
        >
          {previewState.status === 'loading' ? 'Generating preview…' : 'Generate preview'}
        </button>
        <div aria-live="polite" aria-atomic="true">
          {previewState.status === 'loading' && (
            <p className="preview-loading" role="status">
              Checking the flight CSV and generating waypoints…
            </p>
          )}
          {previewState.status === 'success' && (
            <section className="preview-summary" aria-labelledby="preview-title">
              <h2 id="preview-title">Preview ready</h2>
              <dl className="preview-metrics">
                <div><dt>CSV samples</dt><dd>{previewState.preview.sample_count.toLocaleString()}</dd></div>
                <div><dt>Waypoints</dt><dd>{previewState.preview.waypoint_count.toLocaleString()}</dd></div>
                <div><dt>Flight duration</dt><dd>{previewState.preview.duration_s.toLocaleString(undefined, { maximumFractionDigits: 3 })} s</dd></div>
              </dl>
              <p className="next-step">
                Waypoint interval: {previewState.preview.downsample_sec} s.
                {' '}Route and altitude charts are the next step. The simulation has not run.
              </p>
            </section>
          )}
        </div>
        {previewState.status === 'error' && (
          <div className="preview-error" role="alert">
            <h2>Preview could not be generated</h2>
            <p>{previewState.message}</p>
            <p>Check the file or local API, then choose Generate preview to retry.</p>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
