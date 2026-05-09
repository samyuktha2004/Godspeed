import { useRef, useState } from 'react'
import { useUIStore } from '@/stores/uiStore'
import { ApiError } from '@/lib/http'
import { env } from '@/config/env'
import { cn } from '@/lib/utils'

const ACCEPTED = '.pdf,.docx,.doc,.txt,.md,.csv,.xlsx,.xls'
const ACCEPTED_SET = new Set(ACCEPTED.split(','))
const MAX_SIZE_BYTES = 50 * 1024 * 1024 // 50 MB

interface UploadResult {
  filename: string
  task_id:  string
}

interface Props {
  teamId?: string
  onQueued?: (result: UploadResult) => void
}

export function FileUploadWidget({ teamId = 'default', onQueued }: Props) {
  const inputRef              = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [pending, setPending]   = useState<File | null>(null)
  const [loading, setLoading]   = useState(false)
  const [result, setResult]     = useState<UploadResult | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const addToast              = useUIStore((s) => s.addToast)

  const validate = (file: File): string | null => {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase()
    if (!ACCEPTED_SET.has(ext)) return `Unsupported type (${ext}). Accepted: PDF, DOCX, TXT, MD, CSV, XLSX`
    if (file.size > MAX_SIZE_BYTES) return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max 50 MB`
    return null
  }

  const pick = (file: File) => {
    setResult(null)
    const err = validate(file)
    setFileError(err)
    setPending(err ? null : file)
  }

  const upload = async () => {
    if (!pending) return
    setLoading(true)
    try {
      const form = new FormData()
      form.append('file', pending)
      form.append('team_id', teamId)

      const res = await fetch(`${env.apiBaseUrl}/api/ingest/file`, {
        method:      'POST',
        credentials: 'include',
        body:        form,
        // No Content-Type — browser sets multipart boundary automatically
      })

      if (!res.ok) {
        const requestId = res.headers.get('X-Request-ID') ?? undefined
        const text = await res.text().catch(() => res.statusText)
        if (res.status >= 500) {
          addToast({
            type:    'error',
            message: requestId ? `Upload error [${requestId}]` : 'Upload failed — server error',
          })
        } else {
          addToast({ type: 'error', message: text || 'Upload failed' })
        }
        throw new ApiError(res.status, text, requestId)
      }

      const data = await res.json() as UploadResult
      setResult(data)
      setPending(null)
      onQueued?.(data)
      addToast({ type: 'success', message: `${data.filename} queued for processing` })
    } catch (err) {
      if (!(err instanceof ApiError)) {
        addToast({ type: 'error', message: 'Upload failed — no connection' })
      }
    } finally {
      setLoading(false)
    }
  }

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) pick(file)
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
        className={cn(
          'flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors',
          dragging
            ? 'border-brand bg-brand/5'
            : 'border-stone-200 hover:border-brand/50 dark:border-stone-700',
        )}
        aria-label="Upload file — drag and drop or click to browse"
      >
        <span className="text-2xl" aria-hidden>📄</span>
        <p className="text-sm font-medium text-stone-700 dark:text-stone-300">
          Drag a file here or <span className="text-brand underline">browse</span>
        </p>
        <p className="text-xs text-stone-400">PDF · DOCX · TXT · MD · CSV · XLSX — max 50 MB</p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED}
        className="hidden"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) pick(f) }}
      />

      {/* Validation error */}
      {fileError && (
        <p className="text-xs text-red-600 dark:text-red-400">{fileError}</p>
      )}

      {/* Pending file preview */}
      {pending && (
        <div className="flex items-center justify-between rounded-lg border border-surface-subtle px-4 py-3">
          <div>
            <p className="text-sm font-medium">{pending.name}</p>
            <p className="text-xs text-stone-500">{(pending.size / 1024).toFixed(0)} KB</p>
          </div>
          <button
            onClick={upload}
            disabled={loading}
            className="rounded-lg bg-brand px-4 py-1.5 text-xs font-medium text-white hover:bg-brand-dark disabled:opacity-60"
          >
            {loading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      )}

      {/* Success result */}
      {result && (
        <div className="rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm dark:border-green-800 dark:bg-green-950/30">
          <p className="font-medium text-green-700 dark:text-green-400">Queued — processing in background</p>
          <p className="mt-0.5 font-mono text-xs text-stone-500">Task {result.task_id.slice(0, 12)}…</p>
        </div>
      )}
    </div>
  )
}
