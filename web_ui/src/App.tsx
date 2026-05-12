/**
 * Layout shell — top nav + filter bar + page outlet.
 *
 * Five routes, all of them eager. `/` redirects to `/inbox` because Inbox
 * is the natural landing page for the support team.
 */
import { Navigate, NavLink, Route, Routes } from 'react-router-dom'
import { FilterBar } from '@/components/FilterBar'
import { HealthBadge } from '@/components/HealthBadge'
import { cn } from '@/lib/utils'
import InboxPage from '@/pages/InboxPage'
import DraftsPage from '@/pages/DraftsPage'
import SpikesPage from '@/pages/SpikesPage'
import KnowledgePage from '@/pages/KnowledgePage'
import AnalyticsPage from '@/pages/AnalyticsPage'

const NAV = [
  { to: '/inbox', label: 'Inbox' },
  { to: '/drafts', label: 'Drafts' },
  { to: '/spikes', label: 'Spikes' },
  { to: '/knowledge', label: 'Knowledge' },
  { to: '/analytics', label: 'Analytics' },
]

export default function App() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="flex items-center gap-6 px-6 py-3">
          <div className="text-sm font-semibold tracking-tight">
            Support Automation
          </div>
          <nav className="flex items-center gap-1">
            {NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  cn(
                    'rounded-md px-3 py-1.5 text-sm transition-colors',
                    isActive
                      ? 'bg-secondary text-secondary-foreground'
                      : 'text-muted-foreground hover:bg-secondary/60 hover:text-foreground',
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
          <div className="ml-auto">
            <HealthBadge />
          </div>
        </div>
        <FilterBar />
      </header>

      <main>
        <Routes>
          <Route path="/" element={<Navigate to="/inbox" replace />} />
          <Route path="/inbox" element={<InboxPage />} />
          <Route path="/drafts" element={<DraftsPage />} />
          <Route path="/spikes" element={<SpikesPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="*" element={<Navigate to="/inbox" replace />} />
        </Routes>
      </main>
    </div>
  )
}
