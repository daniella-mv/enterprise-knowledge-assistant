// API client. Typed JSON calls + an SSE-streaming chat helper for the
// backend's event: token / event: done / event: error protocol.

import type {
  Citation,
  Document,
  DocumentList,
  HealthResponse,
} from '../types'

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })

  if (!response.ok) {
    let code: string | undefined
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json()
      code = body?.error?.code
      message = body?.error?.message ?? body?.detail ?? message
    } catch {
      // body not JSON; keep default message
    }
    throw new ApiError(message, response.status, code)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

// --- Health -------------------------------------------------------------

export const getHealth = () => api<HealthResponse>('/health')

// --- Documents ----------------------------------------------------------

export const listDocuments = () => api<DocumentList>('/api/documents')

export const getDocument = (id: string) => api<Document>(`/api/documents/${id}`)

export async function uploadDocument(file: File): Promise<Document> {
  const formData = new FormData()
  formData.append('file', file)
  const resp = await fetch('/api/documents', { method: 'POST', body: formData })
  if (!resp.ok) {
    let message = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      message = body?.error?.message ?? body?.detail ?? message
    } catch {
      /* keep default */
    }
    throw new ApiError(message, resp.status)
  }
  return (await resp.json()) as Document
}

export const deleteDocument = (id: string) =>
  api<void>(`/api/documents/${id}`, { method: 'DELETE' })

// --- Chat (SSE) ---------------------------------------------------------

export interface ChatStreamCallbacks {
  onToken: (delta: string) => void
  onDone: (citations: Citation[]) => void
  onError: (message: string) => void
}

/**
 * POST /api/chat as SSE. Calls the appropriate callback for each event.
 * Returns an AbortController so the caller can cancel the stream.
 */
export function streamChat(
  message: string,
  topK: number,
  callbacks: ChatStreamCallbacks,
): AbortController {
  const controller = new AbortController()

  void (async () => {
    let resp: Response
    try {
      resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, top_k: topK }),
        signal: controller.signal,
      })
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        callbacks.onError(`Network error: ${(e as Error).message}`)
      }
      return
    }

    if (!resp.ok || !resp.body) {
      callbacks.onError(`HTTP ${resp.status}`)
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        // Normalize line endings: SSE spec allows \n, \r, or \r\n.
        // sse-starlette uses \r\n; we collapse to \n for a single split path.
        buffer += decoder
          .decode(value, { stream: true })
          .replace(/\r\n/g, '\n')
          .replace(/\r/g, '\n')

        // Each SSE message ends with a blank line (\n\n in normalized form).
        let sep: number
        while ((sep = buffer.indexOf('\n\n')) !== -1) {
          const block = buffer.slice(0, sep)
          buffer = buffer.slice(sep + 2)

          let event = 'message'
          const dataLines: string[] = []
          for (const line of block.split('\n')) {
            if (line.startsWith('event:')) {
              event = line.slice(6).trim()
            } else if (line.startsWith('data:')) {
              // Per SSE spec, strip ONE leading space if present.
              const raw = line.slice(5)
              dataLines.push(raw.startsWith(' ') ? raw.slice(1) : raw)
            }
          }
          const data = dataLines.join('\n')

          if (event === 'token') {
            callbacks.onToken(data)
          } else if (event === 'done') {
            try {
              const parsed = JSON.parse(data) as { citations: Citation[] }
              callbacks.onDone(parsed.citations ?? [])
            } catch {
              callbacks.onDone([])
            }
          } else if (event === 'error') {
            try {
              const parsed = JSON.parse(data) as { message: string }
              callbacks.onError(parsed.message ?? 'unknown error')
            } catch {
              callbacks.onError(data)
            }
          }
        }
      }
    } catch (e: unknown) {
      if ((e as Error).name !== 'AbortError') {
        callbacks.onError(`Stream error: ${(e as Error).message}`)
      }
    }
  })()

  return controller
}
