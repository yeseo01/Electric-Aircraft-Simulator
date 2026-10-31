import { useEffect, useRef, useState } from 'react'
import type * as Plotly from 'plotly.js'
import type { FlightPreview } from '../../api/flightPreviews'
import { loadPlotly3d } from './plotly3dRuntime'
import { initialCamera, route3dFigure } from './route3dFigure'

export default function FlightRoute3D({ preview }: { preview: FlightPreview }) {
  const hostRef = useRef<HTMLDivElement>(null)
  const resetViewRef = useRef<(() => void) | null>(null)
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading')

  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    let disposed = false
    let ready = false
    let plotly: typeof Plotly | undefined
    // Each effect owns its node, so a late async render cannot erase a newer plot.
    const graph = document.createElement('div')
    graph.className = 'chart-canvas'
    host.appendChild(graph)
    setStatus('loading')
    async function resizePlot() {
      try {
        await plotly?.Plots.resize(graph)
      } catch {
        if (!disposed) setStatus('error')
      }
    }
    const observer = new ResizeObserver(() => {
      if (ready && !disposed) void resizePlot()
    })

    async function draw() {
      try {
        plotly = await loadPlotly3d()
        if (disposed) return
        const figure = route3dFigure(preview)
        await plotly.newPlot(graph, figure.data, figure.layout, figure.config)
        if (disposed) {
          plotly.purge(graph)
          return
        }
        ready = true
        observer.observe(host!)
        resetViewRef.current = () => {
          const update: Partial<Plotly.Layout> & { 'scene.camera': Partial<Plotly.Camera> } = {
            'scene.camera': initialCamera(),
          }
          void plotly!.relayout(graph, update).catch(() => {
            if (!disposed) setStatus('error')
          })
        }
        setStatus('ready')
      } catch {
        plotly?.purge(graph)
        if (!disposed) setStatus('error')
      }
    }
    void draw()
    return () => {
      disposed = true
      observer.disconnect()
      resetViewRef.current = null
      if (ready) plotly?.purge(graph)
      graph.remove()
    }
  }, [preview])

  return (
    <>
      <div className="flight-chart flight-chart--3d">
        <div className="chart-canvas" ref={hostRef} role="img"
          aria-label={`3D flight route with ${preview.waypoint_count} waypoints. East, north, and relative pressure altitude in meters, at equal scale.`} />
        {status === 'loading' && <p className="spatial-status" role="status">Preparing 3D view…</p>}
        {status === 'error' && <p className="spatial-status spatial-error" role="alert">
          The 3D view could not be loaded. Check WebGL support and your connection, then generate the preview again. The 2D charts remain available.
        </p>}
      </div>
      <div className="spatial-controls">
        <span>Drag to rotate · Scroll to zoom</span>
        <button className="reset-view" type="button" disabled={status !== 'ready'} onClick={() => resetViewRef.current?.()}>Reset view</button>
      </div>
    </>
  )
}
