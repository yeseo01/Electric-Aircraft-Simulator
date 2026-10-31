import { afterEach, describe, expect, it, vi } from 'vitest'
import { createFlightPreview } from './flightPreviews'
import { previewFixture } from '../test/previewFixture'

afterEach(() => vi.unstubAllGlobals())

function runRequest() {
  return createFlightPreview(new File(['synthetic'], 'flight.csv'), new AbortController().signal)
}

describe('flight preview API client', () => {
  it('posts the selected file as multipart with the interval and abort signal', async () => {
    const payload = previewFixture()
    const fetchMock = vi.fn().mockResolvedValue(Response.json(payload))
    vi.stubGlobal('fetch', fetchMock)
    const file = new File(['synthetic'], 'flight.csv')
    const signal = new AbortController().signal
    expect(await createFlightPreview(file, signal)).toEqual(payload)
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/flight-previews')
    expect(options.method).toBe('POST')
    expect(options.signal).toBe(signal)
    expect(options.body).toBeInstanceOf(FormData)
    expect(options.body.get('file')).toBe(file)
    expect(options.body.get('downsample_sec')).toBe('1.0')
    expect(options.headers).toBeUndefined()
  })

  it('uses issue codes and locations instead of displaying arbitrary backend text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({
      error: {
        code: 'invalid_preview_input', message: 'private server text',
        issues: [{ code: 'missing_column', message: 'private server text', column: 'LAT', row: 1 }],
      },
    }, { status: 422 })))
    await expect(runRequest()).rejects.toThrow('A required column is missing. Column: LAT. CSV line: 1.')
  })

  it.each([
    [413, 'The upload exceeds the size limit'],
    [422, 'The CSV could not be validated'],
    [500, 'Check that the local API is running on port 8000'],
    [404, 'HTTP 404'],
  ])('handles HTTP %s even with a non-JSON error response', async (status, message) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>error</html>', { status })))
    await expect(runRequest()).rejects.toThrow(message)
  })

  it('handles whole-request size errors from the middleware', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({
      error: { code: 'request_too_large', issues: [] },
    }, { status: 413 })))
    await expect(runRequest()).rejects.toThrow('The upload exceeds the request size limit.')
  })

  it('provides guidance on network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(runRequest()).rejects.toThrow('Check that the frontend and local API are running')
  })

  it('rejects unreadable success responses', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('<html>not JSON</html>')))
    await expect(runRequest()).rejects.toThrow('unreadable response')
  })

  it.each([
    { sample_count: 3 },
    { ...previewFixture(), waypoint_count: 99 },
    { ...previewFixture(), duration_s: '2' },
    { ...previewFixture(), waypoints: [null, null] },
  ])('rejects malformed success payload %#', async (payload) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json(payload)))
    await expect(runRequest()).rejects.toThrow('unexpected result')
  })

  it('preserves cancellation rather than reporting a network error', async () => {
    const controller = new AbortController()
    controller.abort()
    const cancelled = new DOMException('Aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(cancelled))
    await expect(createFlightPreview(new File(['synthetic'], 'flight.csv'), controller.signal))
      .rejects.toBe(cancelled)
  })
})
