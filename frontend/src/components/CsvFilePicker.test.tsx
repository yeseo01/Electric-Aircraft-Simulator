import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import App from '../App'

function csv(name = 'flight.csv', contents = 'time(ms),LAT,LNG,PRESSURE_ALT\n') {
  return new File([contents], name, { type: 'text/csv' })
}

function dropFiles(files: File[]) {
  fireEvent.drop(screen.getByRole('group', { name: 'CSV drop area' }), {
    dataTransfer: { files, types: ['Files'] },
  })
}

describe('CSV file selection', () => {
  it('selects, replaces, removes, and reselects a file without a network request', async () => {
    const fetchSpy = vi.spyOn(window, 'fetch')
    const user = userEvent.setup()
    render(<App />)
    const input = screen.getByLabelText('Flight CSV file')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()

    const first = csv()
    await user.upload(input, first)
    expect(screen.getByRole('status')).toHaveTextContent('flight.csv')
    expect(screen.getByRole('status')).toHaveTextContent(`${first.size} bytes`)
    expect(screen.getByRole('button', { name: 'Change CSV' })).toBeInTheDocument()

    await user.upload(input, csv('second.csv'))
    expect(screen.getByRole('status')).toHaveTextContent('second.csv')
    expect(screen.queryByText('flight.csv')).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Remove file' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    await user.upload(input, first)
    expect(screen.getByRole('status')).toHaveTextContent('flight.csv')
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('opens the native file input from a keyboard-accessible button', async () => {
    const user = userEvent.setup()
    render(<App />)
    const inputClick = vi.spyOn(screen.getByLabelText('Flight CSV file'), 'click')
    await user.tab()
    expect(screen.getByRole('button', { name: 'Choose CSV' })).toHaveFocus()
    await user.keyboard('{Enter}')
    expect(inputClick).toHaveBeenCalledOnce()
    inputClick.mockRestore()
  })

  it('accepts a dropped CSV with an uppercase extension and no MIME type', () => {
    render(<App />)
    dropFiles([new File(['synthetic'], 'FLIGHT.CSV')])
    expect(screen.getByRole('status')).toHaveTextContent('FLIGHT.CSV')
  })

  it('keeps the drop highlight while moving between children', () => {
    render(<App />)
    const area = screen.getByRole('group', { name: 'CSV drop area' })
    const button = screen.getByRole('button', { name: 'Choose CSV' })
    const transfer = { dataTransfer: { types: ['Files'] } }
    fireEvent.dragEnter(area, transfer)
    fireEvent.dragEnter(button, transfer)
    fireEvent.dragLeave(button, transfer)
    expect(area).toHaveAttribute('data-dragging', 'true')
    dropFiles([csv()])
    expect(area).toHaveAttribute('data-dragging', 'false')
  })

  it.each([
    ['wrong extension', () => [new File(['text'], 'flight.txt')], /\.csv extension/],
    ['empty file', () => [csv('empty.csv', '')], /empty/],
    ['oversized file', () => [new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'large.csv')], /exceeds 10 MiB/],
    ['multiple files', () => [csv('one.csv'), csv('two.csv')], /one CSV file/],
  ])('rejects %s and clears the previous selection', (_name, files, message) => {
    render(<App />)
    dropFiles([csv()])
    dropFiles(files())
    expect(screen.getByRole('alert')).toHaveTextContent(message)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
    dropFiles([csv('recovered.csv')])
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('recovered.csv')
  })

  it('accepts the exact 10 MiB boundary', () => {
    render(<App />)
    dropFiles([new File([new Uint8Array(10 * 1024 * 1024)], 'limit.csv')])
    expect(screen.getByRole('status')).toHaveTextContent('10.0 MiB')
  })

  it('preserves the selection if the file chooser is cancelled', () => {
    render(<App />)
    dropFiles([csv()])
    fireEvent.change(screen.getByLabelText('Flight CSV file'), { target: { files: [] } })
    expect(screen.getByRole('status')).toHaveTextContent('flight.csv')
  })

  it('prevents file drops outside the target from navigating away', () => {
    render(<App />)
    const event = new Event('drop', { bubbles: true, cancelable: true })
    Object.defineProperty(event, 'dataTransfer', { value: { types: ['Files'] } })
    fireEvent(window, event)
    expect(event.defaultPrevented).toBe(true)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
