import { describe, expect, it } from 'vitest'
import { previewFixture } from '../../test/previewFixture'
import { initialCamera, route3dFigure } from './route3dFigure'

function flight() {
  return {
    ...previewFixture(), waypoint_count: 3, duration_s: 10,
    waypoints: [
      { time_s: 0, east_m: 0, north_m: 0, relative_altitude_m: 0 },
      { time_s: 3, east_m: 200, north_m: 100, relative_altitude_m: -20 },
      { time_s: 10, east_m: -50, north_m: 300, relative_altitude_m: 80 },
    ],
  }
}

describe('3D route figure', () => {
  it('maps east/north/relative pressure altitude and time without sorting the flight', () => {
    const figure = route3dFigure(flight())
    expect(figure.data).toMatchObject([
      { type: 'scatter3d', x: [0, 200, -50], y: [0, 100, 300], z: [0, -20, 80], customdata: [0, 3, 10] },
      { name: 'Start', x: [0], y: [0], z: [0], customdata: [0] },
      { name: 'End', x: [-50], y: [300], z: [80], customdata: [10] },
    ])
    expect(figure.layout.scene).toMatchObject({
      dragmode: 'orbit',
      xaxis: { title: { text: 'East (m)' } },
      yaxis: { title: { text: 'North (m)' } },
      zaxis: { title: { text: 'Δ pressure alt (m)' } },
    })
  })

  it.each([flight(), previewFixture()])('preserves equal meter scale and fits stationary or moving flights in the camera volume', preview => {
    const { scene } = route3dFigure(preview).layout
    const span = (range: readonly unknown[] | undefined) => Number(range![1]) - Number(range![0])
    const aspect = scene!.aspectratio!
    expect(scene!.aspectmode).toBe('manual')
    expect(aspect.x! / span(scene!.xaxis!.range)).toBeCloseTo(aspect.y! / span(scene!.yaxis!.range))
    expect(aspect.x! / span(scene!.xaxis!.range)).toBeCloseTo(aspect.z! / span(scene!.zaxis!.range))
    expect(Math.max(aspect.x!, aspect.y!, aspect.z!)).toBe(1)
    expect(Math.min(aspect.x!, aspect.y!, aspect.z!)).toBeGreaterThan(0)
  })

  it('returns a fresh reset camera so renderer mutations do not change the default', () => {
    const camera = initialCamera()
    camera.eye!.x = 100
    expect(initialCamera().eye!.x).toBe(1.2)
  })
})
