/**
 * Analytics — daily volume (area chart) and category mix (horizontal bar).
 *
 * Both charts use the same scope filter (app/platform/channel) and a
 * per-page range selector (7d / 30d / 90d). Recharts handles responsive
 * sizing; we just give it a fixed-height container.
 */
import { useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useCategoryMix, useVolume, type VolumeBucket } from '@/api/client'
import { useFilters } from '@/hooks/useFilters'
import { Card, CardContent } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

const RANGES = [
  { value: '7', label: 'Last 7 days' },
  { value: '14', label: 'Last 14 days' },
  { value: '30', label: 'Last 30 days' },
  { value: '90', label: 'Last 90 days' },
]

export default function AnalyticsPage() {
  const { filters } = useFilters()
  const [rangeDays, setRangeDays] = useState<number>(14)

  const volumeQuery = useVolume({
    range_days: rangeDays,
    app: filters.app,
    platform: filters.platform,
    channel: filters.channel,
  })
  const categoriesQuery = useCategoryMix({
    range_days: rangeDays,
    app: filters.app,
    platform: filters.platform,
    channel: filters.channel,
  })

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-lg font-semibold">Analytics</h2>
        <Select
          value={String(rangeDays)}
          onValueChange={(value) => setRangeDays(Number(value))}
        >
          <SelectTrigger className="h-8 w-[180px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RANGES.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <CardContent className="pt-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Daily feedback volume
            </h3>
            {volumeQuery.isLoading && (
              <p className="text-muted-foreground">Loading…</p>
            )}
            {volumeQuery.data && (
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={prepareVolume(volumeQuery.data.buckets ?? [])}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#94a3b8" strokeOpacity={0.2} />
                    <XAxis dataKey="bucket_date" fontSize={11} />
                    <YAxis allowDecimals={false} fontSize={11} />
                    <Tooltip />
                    <Area
                      type="monotone"
                      dataKey="total"
                      stroke="hsl(var(--primary))"
                      fill="hsl(var(--primary))"
                      fillOpacity={0.18}
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-4">
            <h3 className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
              Category mix
            </h3>
            {categoriesQuery.isLoading && (
              <p className="text-muted-foreground">Loading…</p>
            )}
            {categoriesQuery.data && (
              <>
                <p className="mb-2 text-xs text-muted-foreground">
                  {categoriesQuery.data.total_classified_feedback} classified
                  feedback{categoriesQuery.data.total_classified_feedback === 1 ? '' : 's'}
                </p>
                <div className="h-72">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      layout="vertical"
                      data={prepareCategories(categoriesQuery.data.categories ?? [])}
                      margin={{ left: 80 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#94a3b8" strokeOpacity={0.2} />
                      <XAxis type="number" allowDecimals={false} fontSize={11} />
                      <YAxis dataKey="label" type="category" fontSize={11} width={140} />
                      <Tooltip />
                      <Bar
                        dataKey="count"
                        fill="hsl(var(--primary))"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function prepareVolume(buckets: VolumeBucket[]) {
  return buckets.map((bucket) => ({
    bucket_date: bucket.bucket_date,
    total: bucket.total,
  }))
}

function prepareCategories(
  categories: { category: string; sub_category?: string | null; count: number }[],
) {
  return categories.map((row) => ({
    label: row.sub_category
      ? `${row.category} / ${row.sub_category}`
      : row.category,
    count: row.count,
  }))
}
