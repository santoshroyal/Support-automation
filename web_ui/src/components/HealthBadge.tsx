/**
 * Small status pill in the header showing the API's health.
 * Polls /api/health every 60s via TanStack Query.
 */
import { useHealth } from '@/api/client'
import { cn } from '@/lib/utils'

export function HealthBadge() {
  const { data, isError, isLoading } = useHealth()

  let label = 'Checking…'
  let dotClass = 'bg-muted-foreground'

  if (isError) {
    label = 'API offline'
    dotClass = 'bg-destructive'
  } else if (!isLoading && data) {
    label = data.status === 'healthy' ? 'API healthy' : `API ${data.status}`
    dotClass = data.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <span className={cn('inline-block h-2 w-2 rounded-full', dotClass)} />
      <span>{label}</span>
    </div>
  )
}
