'use client'

import Link from 'next/link'
import { useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { AlertCircle, ArrowRight, CheckCircle2, Download, FileSpreadsheet, FileUp, Plug, UploadCloud } from 'lucide-react'
import { ApiError } from '@/lib/api-client'
import { getSession } from '@/lib/session'
import { createCsvConnector, uploadCsv } from '@/services/connectors.service'
import type { CsvUploadResponse } from '@/types'

function formatFileSize(size: number): string {
  return size < 1024 * 1024 ? `${Math.ceil(size / 1024)} KB` : `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function formatSyncedAt(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

export default function ConnectorSetupPage() {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const [file, setFile] = useState<File | null>(null)
  const [dataSourceId, setDataSourceId] = useState<string | null>(null)
  const [result, setResult] = useState<CsvUploadResponse | null>(null)
  const [error, setError] = useState('')
  const [uploading, setUploading] = useState(false)

  function selectFile(candidate: File | undefined) {
    setError('')
    setResult(null)
    if (!candidate) return
    if (!candidate.name.toLowerCase().endsWith('.csv')) {
      setFile(null)
      setError('Choose a CSV file to continue.')
      return
    }
    setFile(candidate)
  }

  async function handleUpload() {
    if (!file) {
      setError('Choose a CSV file before uploading.')
      return
    }

    const session = getSession()
    if (!session) {
      router.push('/login')
      return
    }

    setError('')
    setUploading(true)
    try {
      const sourceId = dataSourceId ?? (await createCsvConnector(session.access_token)).data_source_id
      setDataSourceId(sourceId)
      setResult(await uploadCsv(session.access_token, sourceId, file))
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'The upload could not be completed. Please try again.')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="auth-card auth-card-wide">
      <div className="setup-step"><Plug /> Step 2 of 2 · optional</div>
      <h1>Upload marketing data</h1>
      <p className="auth-lede">Upload a CSV to import campaign data safely. Sawakli never asks for provider passwords or tokens here.</p>
      {error && <div className="error-alert" role="alert"><AlertCircle />{error}</div>}

      <section aria-labelledby="csv-upload-title" className="connector-section">
        <div className="connector-heading"><FileSpreadsheet /><div><h2 id="csv-upload-title">CSV import</h2><p>Supported now: secure parsing, raw evidence, and canonical data import.</p></div></div>
        <div className="csv-template">
          <div>
            <strong>Need a template?</strong>
            <p>Use the approved sample with date, campaign name, platform, spend, impressions, clicks, conversions, and revenue.</p>
          </div>
          <a className="btn btn-secondary" href="/samples/sawakli-campaign-data.csv" download>
            <Download /> Download sample CSV
          </a>
        </div>
        <input aria-label="CSV file" ref={inputRef} className="sr-only" id="csv-file" type="file" accept=".csv,text/csv" onChange={(event) => selectFile(event.target.files?.[0])} />
        <button className="upload-zone" type="button" onClick={() => inputRef.current?.click()} disabled={uploading}>
          {file ? <FileUp /> : <UploadCloud />}
          <span><strong>{file ? file.name : 'Choose a CSV file'}</strong><small>{file ? `${formatFileSize(file.size)} · ready to import` : 'CSV files only'}</small></span>
        </button>
        <button className="btn btn-primary auth-submit" type="button" onClick={handleUpload} disabled={uploading || !file}>
          <UploadCloud />{uploading ? 'Uploading and importing…' : 'Upload and import CSV'}
        </button>
      </section>

      {result && (
        <section className="upload-result" aria-live="polite">
          <CheckCircle2 />
          <div><h2>CSV imported</h2><p>{result.row_count} rows were imported{result.parse_warnings.length ? ` with ${result.parse_warnings.length} warning(s)` : '.'}</p></div>
          {result.parse_warnings.length > 0 && <ul>{result.parse_warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul>}
          <p className="status-note">Sync status: {result.sync_status}. Last synced: {formatSyncedAt(result.last_synced_at)}. Dashboard cards remain demo data until API-02/UI-04 use canonical metrics.</p>
        </section>
      )}

      <section className="connector-unavailable" aria-label="Unavailable connectors"><strong>OAuth connectors</strong><span>Google Ads and GA4 authorization are unavailable until the Connector layer provides a real provider flow.</span></section>
      <button className="btn btn-primary auth-submit" type="button" onClick={() => router.push('/dashboard')} disabled={result?.sync_status !== 'success'}><ArrowRight />Continue to demo dashboard</button>
      <button className="btn btn-secondary auth-submit" type="button" onClick={() => router.push('/dashboard')} disabled={uploading}>Skip for now</button>
      <p className="auth-footer"><Link href="/setup/organization">Back to workspace setup</Link></p>
    </div>
  )
}
