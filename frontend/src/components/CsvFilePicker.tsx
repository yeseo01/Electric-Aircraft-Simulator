import { useEffect, useRef, useState } from 'react'
import type { DragEvent } from 'react'
import './CsvFilePicker.css'

const MAX_FILE_BYTES = 10 * 1024 * 1024

type CsvFilePickerProps = {
  file: File | null
  onFileChange: (file: File | null) => void
}

function validateFiles(files: File[]): string | null {
  if (files.length !== 1) return 'Choose one CSV file at a time.'
  if (!files[0].name.toLowerCase().endsWith('.csv')) {
    return 'Choose a file with a .csv extension.'
  }
  if (files[0].size === 0) return 'This file is empty. Choose a flight CSV.'
  if (files[0].size > MAX_FILE_BYTES) {
    return 'This file exceeds 10 MiB. Choose a smaller CSV.'
  }
  return null
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} bytes`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`
}

export default function CsvFilePicker({ file, onFileChange }: CsvFilePickerProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const dragDepth = useRef(0)
  const [isDragging, setIsDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Dropping a file outside the target must not navigate away from this page.
  useEffect(() => {
    const preventFileNavigation = (event: globalThis.DragEvent) => {
      if (event.dataTransfer?.types.includes('Files')) event.preventDefault()
    }
    const endDrag = () => {
      dragDepth.current = 0
      setIsDragging(false)
    }
    const handleWindowDrop = (event: globalThis.DragEvent) => {
      preventFileNavigation(event)
      endDrag()
    }
    window.addEventListener('dragover', preventFileNavigation)
    window.addEventListener('drop', handleWindowDrop)
    window.addEventListener('dragend', endDrag)
    return () => {
      window.removeEventListener('dragover', preventFileNavigation)
      window.removeEventListener('drop', handleWindowDrop)
      window.removeEventListener('dragend', endDrag)
    }
  }, [])

  const selectFiles = (files: File[]) => {
    const validationError = validateFiles(files)
    setError(validationError)
    onFileChange(validationError ? null : files[0])
  }

  const handleDragEnter = (event: DragEvent<HTMLDivElement>) => {
    if (!event.dataTransfer.types.includes('Files')) return
    event.preventDefault()
    dragDepth.current += 1
    setIsDragging(true)
  }

  return (
    <div className="csv-picker">
      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        aria-label="Flight CSV file"
        hidden
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files ?? [])
          // Reset so choosing the same file again still triggers a change.
          event.currentTarget.value = ''
          if (files.length > 0) selectFiles(files)
        }}
      />
      <div
        className="csv-dropzone"
        role="group"
        aria-label="CSV drop area"
        aria-describedby="csv-hint"
        data-dragging={isDragging}
        onDragEnter={handleDragEnter}
        onDragOver={(event) => {
          if (event.dataTransfer.types.includes('Files')) {
            event.preventDefault()
            event.dataTransfer.dropEffect = 'copy'
          }
        }}
        onDragLeave={() => {
          dragDepth.current = Math.max(0, dragDepth.current - 1)
          if (dragDepth.current === 0) setIsDragging(false)
        }}
        onDrop={(event) => {
          event.preventDefault()
          dragDepth.current = 0
          setIsDragging(false)
          const files = Array.from(event.dataTransfer.files)
          if (files.length > 0) selectFiles(files)
        }}
      >
        <p className="csv-drop-title">
          {isDragging ? 'Drop your flight CSV here' : 'Drag a flight CSV here'}
        </p>
        <p id="csv-hint" className="csv-hint">One .csv file · Up to 10 MiB</p>
        <button className="csv-choose" type="button" onClick={() => inputRef.current?.click()}>
          {file ? 'Change CSV' : 'Choose CSV'}
        </button>
      </div>
      {error && <p className="csv-error" role="alert">{error}</p>}
      {file && (
        <div className="csv-selected">
          <div className="csv-file-details" role="status">
            <span className="csv-file-label">Selected file</span>
            <strong className="csv-file-name">{file.name}</strong>
            <span className="csv-file-size">{formatFileSize(file.size)}</span>
          </div>
          <button
            className="csv-remove"
            type="button"
            onClick={() => {
              onFileChange(null)
              setError(null)
            }}
          >
            Remove file
          </button>
        </div>
      )}
    </div>
  )
}
