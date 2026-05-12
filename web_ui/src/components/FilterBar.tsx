/**
 * The single filter bar that sits above every page.
 *
 * Why one component: the same filter set (app / platform / channel)
 * applies to Inbox, Drafts, Spikes, and Analytics — and users should
 * never have to re-pick the same app on every page. Keeping the
 * selections in the URL via `useFilters` does that automatically.
 */
import { useApps } from '@/api/client'
import { useFilters } from '@/hooks/useFilters'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const PLATFORMS = [
  { value: 'all', label: 'All platforms' },
  { value: 'android', label: 'Android' },
  { value: 'ios', label: 'iOS' },
  { value: 'unknown', label: 'Unknown' },
]

const CHANNELS = [
  { value: 'all', label: 'All channels' },
  { value: 'gmail', label: 'Gmail' },
  { value: 'google_play', label: 'Google Play' },
  { value: 'apple_app_store', label: 'Apple App Store' },
]

export function FilterBar() {
  const { filters, setFilter } = useFilters()
  const { data: apps } = useApps()

  return (
    <div className="flex flex-wrap items-center gap-3 border-b bg-background/95 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <FilterSelect
        label="App"
        value={filters.app ?? 'all'}
        onChange={(value) => setFilter('app', value)}
        options={[
          { value: 'all', label: 'All apps' },
          ...(apps ?? []).map((app) => ({ value: app.slug, label: app.name })),
        ]}
      />
      <FilterSelect
        label="Platform"
        value={filters.platform ?? 'all'}
        onChange={(value) => setFilter('platform', value)}
        options={PLATFORMS}
      />
      <FilterSelect
        label="Channel"
        value={filters.channel ?? 'all'}
        onChange={(value) => setFilter('channel', value)}
        options={CHANNELS}
      />
    </div>
  )
}

type FilterSelectProps = {
  label: string
  value: string
  onChange: (value: string) => void
  options: { value: string; label: string }[]
}

function FilterSelect({ label, value, onChange, options }: FilterSelectProps) {
  return (
    <label className="flex items-center gap-2 text-sm text-muted-foreground">
      <span>{label}</span>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger className="h-8 w-[180px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map((option) => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  )
}
