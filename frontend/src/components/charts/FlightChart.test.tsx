import { StrictMode } from 'react'
import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FlightChart from './FlightChart'
import { previewFixture } from '../../test/previewFixture'

const runtime = vi.hoisted(() => ({ init: vi.fn() }))
vi.mock('echarts/core', () => ({ init: runtime.init, use: vi.fn() }))

const observers: { callback: () => void; observe: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = []
const instances: { setOption: ReturnType<typeof vi.fn>; resize: ReturnType<typeof vi.fn>; dispose: ReturnType<typeof vi.fn> }[] = []

beforeEach(() => {
  observers.length = 0
  instances.length = 0
  runtime.init.mockReset().mockImplementation(() => {
    const instance = { setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }
    instances.push(instance)
    return instance
  })
  vi.stubGlobal('ResizeObserver', class {
    observe = vi.fn()
    disconnect = vi.fn()
    callback: () => void
    constructor(callback: () => void) {
      this.callback = callback
      observers.push(this)
    }
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('React chart lifecycle', () => {
  it('renders a described chart, observes panel size, and disposes on unmount', () => {
    const view = render(<FlightChart kind="route" preview={previewFixture()} />)
    expect(screen.getByRole('img', { name: /Flight route with 2 waypoints/ })).toBeInTheDocument()
    expect(runtime.init).toHaveBeenCalledWith(expect.any(HTMLElement), undefined, { renderer: 'svg' })
    expect(observers[0].observe).toHaveBeenCalledOnce()
    act(() => observers[0].callback())
    expect(instances[0].resize).toHaveBeenCalledTimes(2)
    view.unmount()
    expect(observers[0].disconnect).toHaveBeenCalledOnce()
    expect(instances[0].dispose).toHaveBeenCalledOnce()
  })

  it('rebuilds for a new preview instead of retaining previous flight data', () => {
    const view = render(<FlightChart kind="altitude" preview={previewFixture()} />)
    view.rerender(<FlightChart kind="altitude" preview={{ ...previewFixture(), duration_s: 20 }} />)
    expect(instances[0].dispose).toHaveBeenCalledOnce()
    expect(instances[1].setOption).toHaveBeenCalledWith(expect.objectContaining({
      xAxis: expect.objectContaining({ max: 20 }),
    }), { notMerge: true })
    expect(screen.getByRole('img', { name: /over 20 seconds/ })).toBeInTheDocument()
  })

  it('resizes altitude without resetting the user time window', () => {
    render(<FlightChart kind="altitude" preview={previewFixture()} />)
    act(() => observers[0].callback())
    expect(instances[0].resize).toHaveBeenCalledTimes(2)
    expect(instances[0].setOption).toHaveBeenCalledOnce()
  })

  it('cleans up the first instance during React StrictMode remount', () => {
    const view = render(<StrictMode><FlightChart kind="route" preview={previewFixture()} /></StrictMode>)
    expect(instances).toHaveLength(2)
    expect(instances[0].dispose).toHaveBeenCalledOnce()
    expect(observers[0].disconnect).toHaveBeenCalledOnce()
    view.unmount()
    expect(instances[1].dispose).toHaveBeenCalledOnce()
  })
})
