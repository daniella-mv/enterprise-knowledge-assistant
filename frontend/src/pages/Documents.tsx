import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  deleteDocument,
  listDocuments,
  uploadDocument,
} from '../api/client'
import type { Document, DocumentStatus } from '../types'

const ACCEPTED = '.pdf,.docx,.txt,.md'

export default function Documents() {
  const [docs, setDocs] = useState<Document[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [uploading, setUploading] = useState<string | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const [dragActive, setDragActive] = useState(false)
  const inputRef = useRef<HTMLInputElement | null>(null)

  const refresh = useCallback(async () => {
    try {
      const list = await listDocuments()
      setDocs(list.items)
      setLoadError(null)
    } catch (e: unknown) {
      setLoadError(e instanceof ApiError ? e.message : String(e))
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleFile = useCallback(
    async (file: File) => {
      setUploading(file.name)
      setUploadError(null)
      try {
        await uploadDocument(file)
        await refresh()
      } catch (e: unknown) {
        setUploadError(e instanceof ApiError ? e.message : String(e))
      } finally {
        setUploading(null)
      }
    },
    [refresh],
  )

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files?.[0]
    if (file) void handleFile(file)
  }

  const onSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) void handleFile(file)
    e.target.value = '' // reset so the same file can be picked again
  }

  const onDelete = async (id: string, filename: string) => {
    if (!window.confirm(`Delete "${filename}"? This removes its chunks too.`)) {
      return
    }
    try {
      await deleteDocument(id)
      await refresh()
    } catch (e: unknown) {
      setUploadError(e instanceof ApiError ? e.message : String(e))
    }
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
        <p className="mt-1 text-sm text-slate-600">
          Upload PDFs, Word docs, or plain text. Each file is parsed, chunked,
          embedded, and indexed for semantic search.
        </p>
      </div>

      {/* --- Uploader --- */}
      <div
        className={[
          'rounded-xl border-2 border-dashed bg-white p-8 text-center transition-colors',
          dragActive ? 'border-slate-900 bg-slate-50' : 'border-slate-200',
        ].join(' ')}
        onDragOver={(e) => {
          e.preventDefault()
          setDragActive(true)
        }}
        onDragLeave={() => setDragActive(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED}
          className="hidden"
          onChange={onSelect}
          disabled={!!uploading}
        />
        <div className="text-sm text-slate-600">
          {uploading ? (
            <>
              <p className="font-medium text-slate-900">
                Uploading {uploading}…
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Parsing, chunking, and embedding. This may take 5–30 seconds.
              </p>
            </>
          ) : (
            <>
              <p className="font-medium text-slate-900">
                Drag a file here or{' '}
                <button
                  type="button"
                  className="text-slate-900 underline underline-offset-2 hover:text-slate-700"
                  onClick={() => inputRef.current?.click()}
                >
                  browse
                </button>
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Supported: PDF, DOCX, TXT, MD.
              </p>
            </>
          )}
        </div>
      </div>

      {uploadError && (
        <div className="mt-3 rounded-md bg-red-50 p-3 text-sm text-red-800">
          Upload failed: <code className="text-xs">{uploadError}</code>
        </div>
      )}

      {/* --- Document list --- */}
      <div className="mt-8">
        <h2 className="mb-3 text-sm font-medium text-slate-700">
          Indexed documents
          {docs ? <span className="ml-2 text-slate-400">({docs.length})</span> : null}
        </h2>

        {loadError && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-800">
            Couldn't load documents: <code className="text-xs">{loadError}</code>
          </div>
        )}

        {docs && docs.length === 0 && !loadError && (
          <div className="rounded-md border border-dashed border-slate-200 bg-white p-6 text-center text-sm text-slate-500">
            No documents yet. Upload one above to get started.
          </div>
        )}

        {docs && docs.length > 0 && (
          <ul className="divide-y divide-slate-200 overflow-hidden rounded-xl border border-slate-200 bg-white">
            {docs.map((doc) => (
              <li
                key={doc.id}
                className="flex items-center gap-4 px-4 py-3 text-sm"
              >
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium text-slate-900">
                    {doc.filename}
                  </div>
                  <div className="mt-0.5 text-xs text-slate-500">
                    {doc.chunk_count} chunks · {formatSize(doc.file_size)} ·{' '}
                    {new Date(doc.created_at).toLocaleString()}
                  </div>
                  {doc.error && (
                    <div className="mt-1 text-xs text-red-600">{doc.error}</div>
                  )}
                </div>
                <StatusBadge status={doc.status} />
                <button
                  className="text-xs text-slate-500 underline underline-offset-2 hover:text-red-600"
                  onClick={() => void onDelete(doc.id, doc.filename)}
                >
                  delete
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: DocumentStatus }) {
  const styles: Record<DocumentStatus, string> = {
    pending: 'bg-slate-100 text-slate-700',
    processing: 'bg-amber-100 text-amber-800',
    indexed: 'bg-emerald-100 text-emerald-700',
    failed: 'bg-red-100 text-red-700',
  }
  return (
    <span
      className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status]}`}
    >
      {status}
    </span>
  )
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
