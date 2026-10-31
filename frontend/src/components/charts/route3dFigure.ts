import type { Camera, Config, Data, Layout, SceneAxis } from 'plotly.js'
import type { FlightPreview } from '../../api/flightPreviews'

export function initialCamera(): Partial<Camera> {
  return { eye: { x: 1.2, y: -1.4, z: 1 }, up: { x: 0, y: 0, z: 1 } }
}

function paddedRange(values: number[]): [number, number] {
  let min = Infinity
  let max = -Infinity
  for (const value of values) {
    min = Math.min(min, value)
    max = Math.max(max, value)
  }
  const padding = Math.max((max - min) * 0.08, 10)
  return [min - padding, max + padding]
}

function axis(title: string, range: [number, number]): Partial<SceneAxis> {
  return {
    title: { text: title, font: { size: 10, color: '#a3b9c9' } },
    range,
    showbackground: true, backgroundcolor: '#0b1b29',
    gridcolor: '#2a4355', zerolinecolor: '#406276', linecolor: '#406276',
    tickfont: { size: 9, color: '#91acbe' }, nticks: 4, tickformat: '~s',
    showspikes: false,
  }
}

export function route3dFigure(preview: FlightPreview): {
  data: Data[]; layout: Partial<Layout>; config: Partial<Config>
} {
  const x = preview.waypoints.map(point => point.east_m)
  const y = preview.waypoints.map(point => point.north_m)
  const z = preview.waypoints.map(point => point.relative_altitude_m)
  const times = preview.waypoints.map(point => point.time_s)
  const ranges = [paddedRange(x), paddedRange(y), paddedRange(z)]
  const spans = ranges.map(([min, max]) => max - min)
  const maxSpan = Math.max(...spans)
  const hover = 'Time: %{customdata:.2f} s<br>East: %{x:,.1f} m<br>North: %{y:,.1f} m<br>Relative pressure altitude: %{z:,.1f} m<extra>%{fullData.name}</extra>'

  return {
    data: [
      {
        type: 'scatter3d', name: 'Flight route', mode: 'lines',
        x, y, z, customdata: times, hovertemplate: hover,
        line: { color: '#59d9eb', width: 5 }, connectgaps: false,
      },
      ...([0, x.length - 1].map((index, endpoint): Data => ({
        type: 'scatter3d', name: endpoint === 0 ? 'Start' : 'End', mode: 'markers',
        x: [x[index]], y: [y[index]], z: [z[index]], customdata: [times[index]],
        marker: { color: endpoint === 0 ? '#59d9eb' : '#f3c987', size: 5, symbol: endpoint === 0 ? 'circle' : 'diamond' },
        hovertemplate: hover,
      }))),
    ],
    layout: {
      autosize: true, paper_bgcolor: 'rgba(0,0,0,0)',
      margin: { l: 0, r: 0, t: 8, b: 0 }, showlegend: false,
      font: { family: 'Avenir Next, Segoe UI, sans-serif', color: '#c6dbe6' },
      hoverlabel: { bgcolor: '#102a3d', bordercolor: '#386279', font: { color: '#e6f4fa', size: 11 } },
      scene: {
        bgcolor: 'rgba(0,0,0,0)', dragmode: 'orbit', camera: initialCamera(),
        // Normalize by the longest axis: equal meters without a thin flight
        // expanding beyond the camera's view (Plotly's 'data' mode can do that).
        aspectmode: 'manual',
        aspectratio: { x: spans[0] / maxSpan, y: spans[1] / maxSpan, z: spans[2] / maxSpan },
        xaxis: axis('East (m)', ranges[0]), yaxis: axis('North (m)', ranges[1]),
        zaxis: axis('Δ pressure alt (m)', ranges[2]),
      },
    },
    config: { displayModeBar: false, displaylogo: false, scrollZoom: true, responsive: false },
  }
}
