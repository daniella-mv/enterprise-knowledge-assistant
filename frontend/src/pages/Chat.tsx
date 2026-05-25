import { useEffect, useRef, useState } from 'react'
import { streamChat } from '../api/client'
import type { ChatMessage, Citation } from '../types'

export default function Chat() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [activeCitations, setActiveCitations] = useState<Citation[]>([])
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  // Auto-scroll to the bottom as messages change.
  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  const isStreaming = messages.some((m) => m.isStreaming)

  const send = () => {
    const message = input.trim()
    if (!message || isStreaming) return

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: 'user',
      content: message,
    }
    const assistantId = `a-${Date.now()}`
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      isStreaming: true,
    }
    setMessages((prev) => [...prev, userMsg, assistantMsg])
    setInput('')

    abortRef.current = streamChat(message, 5, {
      onToken: (delta) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + delta } : m,
          ),
        )
      },
      onDone: (citations) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, isStreaming: false, citations }
              : m,
          ),
        )
        setActiveCitations(citations)
      },
      onError: (msg) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, isStreaming: false, error: msg }
              : m,
          ),
        )
      },
    })
  }

  const stop = () => {
    abortRef.current?.abort()
    setMessages((prev) =>
      prev.map((m) => (m.isStreaming ? { ...m, isStreaming: false } : m)),
    )
  }

  return (
    <div className="mx-auto grid h-[calc(100vh-3.5rem)] max-w-6xl grid-cols-1 gap-0 px-6 lg:grid-cols-[1fr_320px]">
      {/* --- Chat column --- */}
      <div className="flex h-full flex-col py-6 lg:pr-6">
        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto pr-1">
          {messages.length === 0 && <EmptyState />}
          {messages.map((m) => (
            <MessageBubble
              key={m.id}
              message={m}
              onCitationClick={() => {
                if (m.citations) setActiveCitations(m.citations)
              }}
            />
          ))}
        </div>

        {/* Composer */}
        <form
          className="mt-4 flex gap-2"
          onSubmit={(e) => {
            e.preventDefault()
            send()
          }}
        >
          <textarea
            className="block min-h-[44px] flex-1 resize-none rounded-md border border-slate-300 bg-white px-3 py-2 text-sm shadow-sm focus:border-slate-900 focus:outline-none"
            placeholder="Ask a question about your documents…"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                send()
              }
            }}
            disabled={isStreaming}
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={stop}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              disabled={!input.trim()}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:bg-slate-300"
            >
              Send
            </button>
          )}
        </form>
      </div>

      {/* --- Citation side panel --- */}
      <aside className="hidden border-l border-slate-200 bg-slate-50 lg:block">
        <div className="sticky top-0 max-h-screen overflow-y-auto p-6">
          <h2 className="mb-3 text-sm font-medium text-slate-700">Sources</h2>
          {activeCitations.length === 0 ? (
            <p className="text-xs text-slate-500">
              Citations from the latest answer will appear here. Each is a
              snippet from a source document.
            </p>
          ) : (
            <ul className="space-y-3">
              {activeCitations.map((c, idx) => (
                <li
                  key={c.short_id}
                  className="rounded-lg border border-slate-200 bg-white p-3 text-xs"
                >
                  <div className="mb-1 flex items-center gap-2 font-medium text-slate-900">
                    <span className="grid h-5 w-5 place-items-center rounded-full bg-slate-900 text-[10px] font-semibold text-white">
                      {idx + 1}
                    </span>
                    <span className="truncate">{c.document_filename}</span>
                  </div>
                  <div className="mb-2 text-[11px] text-slate-500">
                    page {c.page} · score {c.score.toFixed(3)}
                  </div>
                  <p className="leading-relaxed text-slate-700">{c.snippet}</p>
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="rounded-xl border border-dashed border-slate-200 bg-white p-8 text-center">
      <h2 className="text-base font-semibold text-slate-900">
        Ask a question
      </h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-600">
        Answers are grounded in your indexed documents and include inline
        citations. If the system doesn't have enough information, it will say
        so instead of guessing.
      </p>
      <p className="mt-3 text-xs text-slate-500">
        Try: <span className="font-mono">"What is the PTO policy?"</span>
      </p>
    </div>
  )
}

interface BubbleProps {
  message: ChatMessage
  onCitationClick: () => void
}

function MessageBubble({ message, onCitationClick }: BubbleProps) {
  const isUser = message.role === 'user'
  return (
    <div className={isUser ? 'flex justify-end' : 'flex justify-start'}>
      <div
        className={[
          'max-w-2xl rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-slate-900 text-white'
            : 'bg-white text-slate-900 shadow-sm ring-1 ring-slate-200',
        ].join(' ')}
        onClick={!isUser ? onCitationClick : undefined}
      >
        {isUser ? (
          message.content
        ) : message.error ? (
          <span className="text-red-600">⚠ {message.error}</span>
        ) : (
          <RenderedAnswer
            text={message.content}
            citations={message.citations}
            isStreaming={!!message.isStreaming}
          />
        )}
      </div>
    </div>
  )
}

function RenderedAnswer({
  text,
  citations,
  isStreaming,
}: {
  text: string
  citations?: Citation[]
  isStreaming: boolean
}) {
  // Map short_id -> display number based on first appearance in text.
  const displayMap = new Map<string, number>()
  if (citations) {
    citations.forEach((c, i) => displayMap.set(c.short_id, i + 1))
  }

  const parts = text.split(/(\[c_\d+\])/g)

  return (
    <span>
      {parts.map((part, i) => {
        const m = part.match(/^\[c_(\d+)\]$/)
        if (m) {
          const shortId = `c_${m[1]}`
          const num = displayMap.get(shortId) ?? Number(m[1]) + 1
          return (
            <sup
              key={i}
              className="ml-0.5 inline-block min-w-[1.25rem] cursor-pointer rounded-full bg-slate-100 px-1 text-center text-[10px] font-semibold text-slate-700 hover:bg-slate-200"
              title={shortId}
            >
              {num}
            </sup>
          )
        }
        return <span key={i}>{part}</span>
      })}
      {isStreaming && (
        <span
          className="ml-0.5 inline-block h-3 w-1.5 translate-y-0.5 animate-pulse bg-slate-400"
          aria-hidden
        />
      )}
    </span>
  )
}
