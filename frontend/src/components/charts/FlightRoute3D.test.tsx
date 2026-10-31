import { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import FlightRoute3D from './FlightRoute3D'
import { previewFixture } from '../../test/previewFixture'

const runtime = vi.hoisted(() => ({
  load: vi.fn(), newPlot: vi.fn(), purge: vi.fn(), resize: vi.fn(), relayout: vi.fn(),
}))
vi.mock('./plotly3dRuntime', () => ({ loadPlotly3d: runtime.load }))
const observers: { callback: () => void; observe: ReturnType<typeof vi.fn>; disconnect: ReturnType<typeof vi.fn> }[] = []
const api = { newPlot: runtime.newPlot, purge: runtime.purge, Plots: { resize: runtime.resize }, relayout: runtime.relayout }

beforeEach(() => {
  vi.clearAllMocks()
  observers.length = 0
  runtime.load.mockReset().mockResolvedValue(api)
  runtime.newPlot.mockReset().mockResolvedValue(undefined)
  runtime.relayout.mockReset().mockResolvedValue(undefined)
  vi.stubGlobal('ResizeObserver', class {
    observe = vi.fn()
    disconnect = vi.fn()
    callback: () => void
    constructor(callback: () => void) { this.callback = callback; observers.push(this) }
  })
})
afterEach(() => vi.unstubAllGlobals())

async function expectReady() {
  await waitFor(() => expect(screen.getByRole('button', { name: 'Reset view' })).toBeEnabled())
}

describe('3D chart lifecycle', () => {
  it('loads the renderer, creates a described plot, resizes, resets, and purges on unmount', async () => {
    const view = render(<FlightRoute3D preview={previewFixture()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Preparing 3D view')
    await expectReady()
    expect(screen.getByRole('img', { name: /3D flight route with 2 waypoints/ })).toBeInTheDocument()
    expect(runtime.newPlot).toHaveBeenCalledOnce()
    act(() => observers[0].callback())
    expect(runtime.resize).toHaveBeenCalledOnce()
    fireEvent.click(screen.getByRole('button', { name: 'Reset view' }))
    expect(runtime.relayout).toHaveBeenCalledWith(expect.any(HTMLElement), {
      'scene.camera': expect.objectContaining({
        eye: { x: 0.84, y: -0.98, z: 0.7 }, center: { x: 0, y: 0, z: -0.1 },
      }),
    })
    view.unmount()
    expect(runtime.purge).toHaveBeenCalledOnce()
    expect(observers[0].disconnect).toHaveBeenCalledOnce()
  })

  it.each(['download', 'WebGL'])('shows a recoverable message on %s failure', async failure => {
    if (failure === 'download') runtime.load.mockRejectedValueOnce(new Error('Load failed'))
    else runtime.newPlot.mockRejectedValueOnce(new Error('WebGL unavailable'))
    render(<FlightRoute3D preview={previewFixture()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('The 3D view could not be loaded')
    expect(screen.getByRole('button', { name: 'Reset view' })).toBeDisabled()
  })

  it('offers only 1× and 5×, defaults to 5×, and preserves altitude data when switching', async () => {
    render(<FlightRoute3D preview={previewFixture()} />)
    await expectReady()
    expect(screen.getByRole('combobox', { name: 'Vertical display scale' })).toHaveValue('5')
    expect(screen.getAllByRole('option').map(option => (option as HTMLOptionElement).value)).toEqual(['1', '5'])
    expect(screen.getByText(/Height displayed at 5×/)).toBeInTheDocument()
    const initialData = runtime.newPlot.mock.calls[0][1]
    fireEvent.change(screen.getByRole('combobox', { name: 'Vertical display scale' }), { target: { value: '1' } })
    await expectReady()
    expect(runtime.newPlot).toHaveBeenCalledTimes(2)
    expect(runtime.newPlot.mock.calls[1][1]).toEqual(initialData)
    expect(screen.getByRole('img', { name: /Vertical display scale 1 times/ })).toBeInTheDocument()
  })

  it('does not create a plot if an import completes after unmount', async () => {
    let complete!: (value: typeof api) => void
    runtime.load.mockReturnValueOnce(new Promise(resolve => { complete = resolve }))
    const view = render(<FlightRoute3D preview={previewFixture()} />)
    view.unmount()
    await act(async () => { complete(api) })
    expect(runtime.newPlot).not.toHaveBeenCalled()
  })

  it('keeps a late old render isolated from the new flight', async () => {
    let complete!: () => void
    runtime.newPlot.mockReturnValueOnce(new Promise<void>(resolve => { complete = resolve }))
    const view = render(<FlightRoute3D preview={previewFixture()} />)
    await waitFor(() => expect(runtime.newPlot).toHaveBeenCalledOnce())
    const oldGraph = runtime.newPlot.mock.calls[0][0] as HTMLElement
    view.rerender(<FlightRoute3D preview={{ ...previewFixture(), waypoint_count: 20 }} />)
    await expectReady()
    const newGraph = runtime.newPlot.mock.calls[1][0] as HTMLElement
    expect(newGraph).not.toBe(oldGraph)
    expect(oldGraph.isConnected).toBe(false)
    await act(async () => { complete() })
    expect(runtime.purge.mock.calls[0][0]).toBe(oldGraph)
    expect(runtime.purge.mock.calls.some(([graph]) => graph === newGraph)).toBe(false)
    expect(newGraph.isConnected).toBe(true)
  })

  it('works through the development StrictMode setup/cleanup cycle', async () => {
    const view = render(<StrictMode><FlightRoute3D preview={previewFixture()} /></StrictMode>)
    await expectReady()
    expect(runtime.newPlot).toHaveBeenCalledOnce()
    view.unmount()
    expect(runtime.purge).toHaveBeenCalledOnce()
    expect(observers.every(observer => observer.disconnect.mock.calls.length === 1)).toBe(true)
  })
})
