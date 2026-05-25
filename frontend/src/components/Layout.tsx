import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import { ApiError, getHealth } from '../api/client'
import type { HealthResponse } from '../types'

export default function Layout() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [healthErr, setHealthErr] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const tick = async () => {
      try {
        const h = await getHealth()
        if (!cancelled) {
          setHealth(h)
          setHealthErr(null)
        }
      } catch (e: unknown) {
        if (!cancelled) {
          setHealthErr(e instanceof ApiError ? e.message : String(e))
        }
      }
    }
    void tick()
    const interval = setInterval(tick, 30_000)
    return () => {
      cancelled = true
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="flex h-full min-h-screen flex-col bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-6">
          <div className="flex items-center gap-2">
            <div className="grid h-7 w-7 place-items-center rounded-md bg-slate-900 text-xs font-semibold text-white">
              EKA
            </div>
            <span className="text-sm font-semibold tracking-tight">
              Enterprise Knowledge Assistant
            </span>
          </div>

          <nav className="flex items-center gap-1 text-sm">
            <NavTab to="/chat">Chat</NavTab>
            <NavTab to="/documents">Documents</NavTab>
          </nav>

          <div className="ml-auto">
            {healthErr ? (
              <span className="rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-700">
                api unreachable
              </span>
            ) : health ? (
              <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                api healthy · v{health.version}
              </span>
            ) : (
              <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
                checking…
              </span>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>
    </div>
  )
}

function NavTab({ to, children }: { to: string; children: React.ReactNode }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        [
          'rounded-md px-3 py-1.5 font-medium transition-colors',
          isActive
            ? 'bg-slate-100 text-slate-900'
            : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900',
        ].join(' ')
      }
    >
      {children}
    </NavLink>
  )
}
