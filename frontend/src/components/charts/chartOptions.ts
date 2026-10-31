import type { ComposeOption } from 'echarts/core'
import type { LineSeriesOption, ScatterSeriesOption } from 'echarts/charts'
import type { DataZoomComponentOption, GridComponentOption, TooltipComponentOption } from 'echarts/components'
import type { FlightPreview } from '../../api/flightPreviews'

export type FlightChartOption = ComposeOption<
  LineSeriesOption | ScatterSeriesOption | GridComponentOption |
  TooltipComponentOption | DataZoomComponentOption
>

const cyan = '#59d9eb'
const amber = '#f3c987'
const routeGrid = { left: 52, right: 16, top: 18, bottom: 38 }
const axis = {
  type: 'value' as const,
  nameLocation: 'middle' as const,
  nameTextStyle: { color: '#a3b9c9', fontSize: 11 },
  axisLabel: {
    color: '#87a1b5', fontSize: 10, hideOverlap: true,
    showMinLabel: false, showMaxLabel: false,
    formatter: (value: number | string) => Number(value).toLocaleString('en-US', { maximumFractionDigits: 2 }),
  },
  axisLine: { show: false },
  axisTick: { show: false },
  splitLine: { lineStyle: { color: '#203447', type: 'dashed' as const } },
  splitNumber: 4,
}
const tooltip: TooltipComponentOption = {
  confine: true,
  renderMode: 'richText',
  backgroundColor: '#102a3d',
  borderColor: '#386279',
  textStyle: { color: '#e6f4fa', fontSize: 12 },
  valueFormatter: (value) => typeof value === 'number'
    ? value.toLocaleString('en-US', { maximumFractionDigits: 2 }) : String(value),
}

function extent(values: number[]): [number, number] {
  let min = Infinity
  let max = -Infinity
  for (const value of values) {
    min = Math.min(min, value)
    max = Math.max(max, value)
  }
  return [min, max]
}

// One meter has the same visual length on both route axes at every panel size.
export function routeBounds(preview: FlightPreview, width: number, height: number) {
  const [eastMin, eastMax] = extent(preview.waypoints.map((point) => point.east_m))
  const [northMin, northMax] = extent(preview.waypoints.map((point) => point.north_m))
  const aspect = Math.max(width - routeGrid.left - routeGrid.right, 1)
    / Math.max(height - routeGrid.top - routeGrid.bottom, 1)
  let eastSpan = Math.max(eastMax - eastMin, 20) * 1.25
  let northSpan = Math.max(northMax - northMin, 20) * 1.25
  if (eastSpan / northSpan < aspect) eastSpan = northSpan * aspect
  else northSpan = eastSpan / aspect
  const eastCenter = (eastMin + eastMax) / 2
  const northCenter = (northMin + northMax) / 2
  return {
    eastMin: eastCenter - eastSpan / 2, eastMax: eastCenter + eastSpan / 2,
    northMin: northCenter - northSpan / 2, northMax: northCenter + northSpan / 2,
  }
}

export function routeOption(preview: FlightPreview, width: number, height: number): FlightChartOption {
  const bounds = routeBounds(preview, width, height)
  const data = preview.waypoints.map((point) => [
    point.east_m, point.north_m, point.time_s, point.relative_altitude_m,
  ])
  const dimensions = ['East (m)', 'North (m)', 'Time (s)', 'Relative pressure altitude (m)']
  const encode = { x: 0, y: 1, tooltip: [2, 0, 1, 3] }
  return {
    animation: false,
    grid: { ...routeGrid },
    tooltip: { ...tooltip, trigger: 'axis', axisPointer: { type: 'cross' } },
    xAxis: { ...axis, name: 'East (m)', nameGap: 25, min: bounds.eastMin, max: bounds.eastMax },
    yAxis: { ...axis, name: 'North (m)', nameGap: 38, min: bounds.northMin, max: bounds.northMax },
    series: [
      {
        name: 'Flight route', type: 'line', data, dimensions, encode,
        showSymbol: false, smooth: false, lineStyle: { color: cyan, width: 2.5 },
        itemStyle: { color: cyan },
      },
      {
        name: 'Start', type: 'scatter', data: [data[0]], dimensions, encode,
        symbol: 'circle', symbolSize: 11, z: 3,
        itemStyle: { color: cyan, borderColor: '#071824', borderWidth: 3 },
        label: { show: true, formatter: 'START', position: 'bottom', color: cyan, fontSize: 9, distance: 4 },
        tooltip: { trigger: 'item' },
      },
      {
        name: 'End', type: 'scatter', data: [data[data.length - 1]], dimensions, encode,
        symbol: 'diamond', symbolSize: 12, z: 4,
        itemStyle: { color: amber, borderColor: '#071824', borderWidth: 2 },
        label: { show: true, formatter: 'END', position: 'top', color: amber, fontSize: 9, distance: 4 },
        tooltip: { trigger: 'item' },
      },
    ],
  }
}

export function altitudeOption(preview: FlightPreview): FlightChartOption {
  return {
    animation: false,
    grid: { left: 52, right: 16, top: 10, bottom: 50 },
    tooltip: { ...tooltip, trigger: 'axis', axisPointer: { type: 'line' } },
    xAxis: { ...axis, name: 'Elapsed time (s)', nameGap: 23, min: 0, max: preview.duration_s },
    yAxis: { ...axis, name: 'Altitude (m)', nameGap: 38, scale: true },
    dataZoom: [
      { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
      {
        type: 'slider', xAxisIndex: 0, filterMode: 'none', bottom: 0,
        left: 52, right: 16, height: 10, showDetail: false,
        borderColor: '#294457', backgroundColor: '#0b1c2b',
        fillerColor: '#59d9eb24', handleStyle: { color: cyan, borderColor: cyan },
        dataBackground: { lineStyle: { color: '#496e86' }, areaStyle: { color: '#1f3c50' } },
        selectedDataBackground: { lineStyle: { color: cyan }, areaStyle: { color: '#59d9eb44' } },
      },
    ],
    series: [{
      name: 'Relative pressure altitude', type: 'line',
      dimensions: ['Elapsed time (s)', 'Relative pressure altitude (m)'],
      encode: { x: 0, y: 1, tooltip: [0, 1] },
      data: preview.waypoints.map((point) => [point.time_s, point.relative_altitude_m]),
      showSymbol: false, smooth: false, lineStyle: { color: cyan, width: 2 },
      itemStyle: { color: cyan },
      areaStyle: {
        origin: 'start',
        color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [
          { offset: 0, color: '#59d9eb40' }, { offset: 1, color: '#59d9eb02' },
        ] },
      },
    }],
  }
}
