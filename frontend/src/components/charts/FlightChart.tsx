import { useEffect, useRef } from 'react'
import { init, use } from 'echarts/core'
import { LineChart, ScatterChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { FlightPreview } from '../../api/flightPreviews'
import { altitudeOption, routeOption } from './chartOptions'

use([LineChart, ScatterChart, DataZoomComponent, GridComponent, TooltipComponent, SVGRenderer])

type FlightChartProps = { kind: 'route' | 'altitude'; preview: FlightPreview }

export default function FlightChart({ kind, preview }: FlightChartProps) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const chart = init(container, undefined, { renderer: 'svg' })
    const draw = () => {
      chart.resize()
      if (kind === 'route') {
        chart.setOption(routeOption(preview, container.clientWidth, container.clientHeight), { notMerge: true })
      }
    }
    if (kind === 'altitude') chart.setOption(altitudeOption(preview), { notMerge: true })
    draw()
    const observer = new ResizeObserver(draw)
    observer.observe(container)
    return () => {
      observer.disconnect()
      chart.dispose()
    }
  }, [kind, preview])

  const description = kind === 'route'
    ? `Flight route with ${preview.waypoint_count} waypoints in local east and north coordinates, meters. Start and end are marked.`
    : `Relative pressure altitude over ${preview.duration_s} seconds, referenced to the first CSV sample, meters.`

  return (
    <div className={`flight-chart flight-chart--${kind}`} role="img" aria-label={description}>
      <div className="chart-canvas" ref={containerRef} aria-hidden="true" />
    </div>
  )
}
