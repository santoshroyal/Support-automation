/**
 * Knowledge-base health — one row per knowledge source with a freshness
 * badge. The freshness policy is defined server-side (see
 * adapters / api routes); the UI just renders the classification.
 */
import { useKnowledgeSources } from '@/api/client'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { formatDateTime } from '@/lib/format'

const FRESHNESS_LABELS: Record<string, string> = {
  fresh: 'Fresh',
  stale: 'Stale',
  very_stale: 'Very stale',
  empty: 'Empty',
}

const FRESHNESS_CLASS: Record<string, string> = {
  fresh: 'bg-emerald-500 text-white hover:bg-emerald-500',
  stale: 'bg-amber-500 text-white hover:bg-amber-500',
  very_stale: 'bg-red-500 text-white hover:bg-red-500',
  empty: 'bg-slate-400 text-white hover:bg-slate-400',
}

const SOURCE_LABELS: Record<string, string> = {
  confluence: 'Confluence',
  jira: 'JIRA',
  google_sheets: 'Google Sheets',
}

export default function KnowledgePage() {
  const { data, isLoading, error } = useKnowledgeSources()

  return (
    <div className="p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">Knowledge base health</h2>
        {data && (
          <p className="text-xs text-muted-foreground">
            {data.total_documents} document{data.total_documents === 1 ? '' : 's'}
            {' · '}
            {data.total_chunks} chunk{data.total_chunks === 1 ? '' : 's'}
          </p>
        )}
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-destructive">Error: {String(error)}</p>}

      {data && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {(data.sources ?? []).map((source) => (
            <Card key={source.source}>
              <CardContent className="pt-4">
                <div className="flex items-baseline justify-between">
                  <h3 className="text-sm font-semibold">
                    {SOURCE_LABELS[source.source] ?? source.source}
                  </h3>
                  <Badge
                    className={cn(
                      'uppercase',
                      FRESHNESS_CLASS[source.freshness] ?? 'bg-slate-500',
                    )}
                  >
                    {FRESHNESS_LABELS[source.freshness] ?? source.freshness}
                  </Badge>
                </div>
                <dl className="mt-3 space-y-1 text-xs text-muted-foreground">
                  <div className="flex justify-between">
                    <dt>Documents</dt>
                    <dd className="font-medium text-foreground">
                      {source.document_count}
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt>Latest update</dt>
                    <dd className="font-medium text-foreground">
                      {formatDateTime(source.latest_document_at)}
                    </dd>
                  </div>
                </dl>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
