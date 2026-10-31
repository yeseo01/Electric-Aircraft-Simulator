import { describe, expect, it } from 'vitest'
import { previewFixture } from '../../test/previewFixture'
import { altitudeOption, routeBounds, routeOption } from './chartOptions'

function flight() {
  return {
    ...previewFixture(), sample_count: 3, waypoint_count: 3, duration_s: 10,
    waypoints: [
      { time_s: 0, east_m: 0, north_m: 0, relative_altitude_m: 0 },
      { time_s: 3, east_m: 200, north_m: 100, relative_altitude_m: -20 },
      { time_s: 10, east_m: -50, north_m: 300, relative_altitude_m: 80 },
    ],
  }
}

describe('flight chart data', () => {
  it('preserves the flown order, east/north units, endpoints, and time metadata', () => {
    const option = routeOption(flight(), 800, 400)
    expect(option.series).toMatchObject([
      { type: 'line', smooth: false, data: [[0, 0, 0, 0], [200, 100, 3, -20], [-50, 300, 10, 80]] },
      { name: 'Start', data: [[0, 0, 0, 0]] },
      { name: 'End', data: [[-50, 300, 10, 80]] },
    ])
    expect(option.xAxis).toMatchObject({ name: 'East (m)' })
    expect(option.yAxis).toMatchObject({ name: 'North (m)' })
  })

  it('uses actual elapsed times and pressure altitude offsets, including negative values', () => {
    const option = altitudeOption(flight())
    expect(option.series).toMatchObject([{
      name: 'Relative pressure altitude', smooth: false,
      data: [[0, 0], [3, -20], [10, 80]],
    }])
    expect(option.xAxis).toMatchObject({ min: 0, max: 10, name: 'Elapsed time (s)' })
    expect(option.dataZoom).toMatchObject([{ xAxisIndex: 0 }, { type: 'slider', xAxisIndex: 0 }])
  })

  it.each([[800, 400], [320, 340], [1200, 380]])('keeps route meters at equal scale in a %sx%s panel', (width, height) => {
    const bounds = routeBounds(flight(), width, height)
    const metersPerPixelX = (bounds.eastMax - bounds.eastMin) / (width - 92)
    const metersPerPixelY = (bounds.northMax - bounds.northMin) / (height - 90)
    expect(metersPerPixelX).toBeCloseTo(metersPerPixelY)
    for (const point of flight().waypoints) {
      expect(point.east_m).toBeGreaterThan(bounds.eastMin)
      expect(point.east_m).toBeLessThan(bounds.eastMax)
      expect(point.north_m).toBeGreaterThan(bounds.northMin)
      expect(point.north_m).toBeLessThan(bounds.northMax)
    }
  })

  it('gives a stationary flight a finite, visible route extent', () => {
    const bounds = routeBounds(previewFixture(), 600, 340)
    expect(bounds.eastMax).toBeGreaterThan(bounds.eastMin)
    expect(bounds.northMax).toBeGreaterThan(bounds.northMin)
    expect(Object.values(bounds).every(Number.isFinite)).toBe(true)
  })
})
