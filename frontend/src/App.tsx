import { useState } from 'react'
import CsvFilePicker from './components/CsvFilePicker'
import './App.css'

function App() {
  const [file, setFile] = useState<File | null>(null)

  return (
    <main className="app">
      <section className="welcome" aria-labelledby="page-title">
        <p className="eyebrow">Electric Aircraft Simulator</p>
        <h1 id="page-title">Flight profile preview</h1>
        <p className="description">Start with your flight log.</p>
        <CsvFilePicker file={file} onFileChange={setFile} />
        <p className="next-step">
          Your file stays in this browser. API upload and waypoint preview are
          coming in the next steps.
        </p>
      </section>
    </main>
  )
}

export default App
