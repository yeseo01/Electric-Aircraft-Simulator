import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { previewFixture } from './test/previewFixture'

afterEach(() => vi.unstubAllGlobals())

function dropFile(name = 'flight.csv') {
  fireEvent.drop(screen.getByRole('group', { name: 'CSV drop area' }), {
    dataTransfer: { files: [new File(['synthetic'], name)], types: ['Files'] },
  })
}

function deferredResponse() {
  let resolve!: (response: Response) => void
  const promise = new Promise<Response>((done) => { resolve = done })
  return { promise, resolve }
}

describe('preview submission flow', () => {
  it('waits for an explicit click, shows loading, prevents duplicates, and renders a summary', async () => {
    const pending = deferredResponse()
    const fetchMock = vi.fn().mockReturnValue(pending.promise)
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)
    expect(screen.getByRole('button', { name: 'Generate preview' })).toBeDisabled()
    dropFile()
    expect(fetchMock).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    const loadingButton = screen.getByRole('button', { name: 'Generating preview…' })
    expect(loadingButton).toBeDisabled()
    expect(screen.getByText('Checking the flight CSV and generating waypoints…')).toBeInTheDocument()
    await user.click(loadingButton)
    expect(fetchMock).toHaveBeenCalledOnce()
    await act(async () => { pending.resolve(Response.json(previewFixture())) })
    const summary = screen.getByRole('region', { name: 'Preview ready' })
    expect(within(summary).getByText('CSV samples').nextElementSibling).toHaveTextContent('3')
    expect(within(summary).getByText('Waypoints').nextElementSibling).toHaveTextContent('2')
    expect(within(summary).getByText('Flight duration').nextElementSibling).toHaveTextContent('2 s')
    expect(screen.getByRole('button', { name: 'Generate preview' })).toBeEnabled()
  })

  it('shows a validation error with its column and line and supports retry', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(Response.json({
        error: { code: 'invalid_preview_input', issues: [{ code: 'missing_column', column: 'LAT', row: 1 }] },
      }, { status: 422 }))
      .mockResolvedValueOnce(Response.json(previewFixture()))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)
    dropFile()
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Column: LAT. CSV line: 1.')
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    expect(await screen.findByRole('region', { name: 'Preview ready' })).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('shows connection guidance on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const user = userEvent.setup()
    render(<App />)
    dropFile()
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Check that the frontend and local API are running')
  })

  it.each(['replace', 'remove', 'invalid replacement'])('clears a completed preview on %s', async (action) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(previewFixture())))
    const user = userEvent.setup()
    render(<App />)
    dropFile()
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    await screen.findByRole('region', { name: 'Preview ready' })
    if (action === 'remove') await user.click(screen.getByRole('button', { name: 'Remove file' }))
    else dropFile(action === 'replace' ? 'second.csv' : 'invalid.txt')
    expect(screen.queryByRole('region', { name: 'Preview ready' })).not.toBeInTheDocument()
    if (action !== 'replace') expect(screen.getByRole('button', { name: 'Generate preview' })).toBeDisabled()
  })

  it('cancels the previous request and ignores its late response after a new file completes', async () => {
    const oldRequest = deferredResponse()
    const fetchMock = vi.fn()
      .mockReturnValueOnce(oldRequest.promise)
      .mockResolvedValueOnce(Response.json({ ...previewFixture(), sample_count: 10 }))
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)
    dropFile('first.csv')
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    const oldSignal = fetchMock.mock.calls[0][1].signal as AbortSignal
    dropFile('second.csv')
    expect(oldSignal.aborted).toBe(true)
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    await screen.findByRole('region', { name: 'Preview ready' })
    await act(async () => { oldRequest.resolve(Response.json(previewFixture())) })
    const summary = screen.getByRole('region', { name: 'Preview ready' })
    expect(within(summary).getByText('CSV samples').nextElementSibling).toHaveTextContent('10')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('cancels an in-flight request when the selected file is removed', async () => {
    const pending = deferredResponse()
    const fetchMock = vi.fn().mockReturnValue(pending.promise)
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    render(<App />)
    dropFile()
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    await user.click(screen.getByRole('button', { name: 'Remove file' }))
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => { pending.resolve(Response.json(previewFixture())) })
    expect(screen.queryByRole('region', { name: 'Preview ready' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Generate preview' })).toBeDisabled()
  })

  it('cancels on unmount', async () => {
    const pending = deferredResponse()
    const fetchMock = vi.fn().mockReturnValue(pending.promise)
    vi.stubGlobal('fetch', fetchMock)
    const user = userEvent.setup()
    const view = render(<App />)
    dropFile()
    await user.click(screen.getByRole('button', { name: 'Generate preview' }))
    view.unmount()
    expect(fetchMock.mock.calls[0][1].signal.aborted).toBe(true)
    await act(async () => { pending.resolve(Response.json(previewFixture())) })
  })
})
