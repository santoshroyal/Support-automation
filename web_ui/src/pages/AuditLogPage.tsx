/**
 * Audit log — what the system did and when.
 *
 * Chronological table of every recorded action, with an actor filter so
 * an on-call person can answer "what did the draft-replies cron do
 * yesterday?" in two clicks. The details column renders the free-form
 * JSON payload as key/value pairs.
 */
import { useState } from 'react'
import { useAuditLog } from '@/api/client'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { formatDateTime, formatRelative } from '@/lib/format'

const ACTORS = [
  { value: 'all', label: 'All actors' },
  { value: 'ingest-feedback', label: 'ingest-feedback' },
  { value: 'classify-and-cluster', label: 'classify-and-cluster' },
  { value: 'sync-knowledge-base', label: 'sync-knowledge-base' },
  { value: 'draft-replies', label: 'draft-replies' },
  { value: 'detect-spikes', label: 'detect-spikes' },
  { value: 'send-digest-hourly', label: 'send-digest-hourly' },
  { value: 'send-digest-daily', label: 'send-digest-daily' },
  { value: 'api', label: 'api' },
]

export default function AuditLogPage() {
  const [actor, setActor] = useState<string>('all')

  const { data, isLoading, error } = useAuditLog({
    actor: actor === 'all' ? undefined : actor,
    limit: 200,
  })

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between gap-4">
        <h2 className="text-lg font-semibold">Audit log</h2>
        <div className="flex items-center gap-3">
          <p className="text-xs text-muted-foreground">
            {data ? `${data.length} entries` : ''}
          </p>
          <Select value={actor} onValueChange={setActor}>
            <SelectTrigger className="h-8 w-[220px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ACTORS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-destructive">Error: {String(error)}</p>}

      {data && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>When</TableHead>
                <TableHead>Actor</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                    <div title={formatDateTime(entry.occurred_at)}>
                      {formatRelative(entry.occurred_at)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge variant="outline">{entry.actor}</Badge>
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {entry.action}
                  </TableCell>
                  <TableCell className="text-xs">
                    <DetailsPills details={entry.details ?? {}} />
                  </TableCell>
                </TableRow>
              ))}
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center text-muted-foreground">
                    No audit entries match the current filter.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}
    </div>
  )
}

function DetailsPills({ details }: { details: Record<string, unknown> }) {
  const entries = Object.entries(details)
  if (entries.length === 0) {
    return <span className="text-muted-foreground">—</span>
  }
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([key, value]) => (
        <span
          key={key}
          className="rounded border bg-background px-1.5 py-0.5"
          title={`${key}: ${String(value)}`}
        >
          <span className="text-muted-foreground">{key}=</span>
          <span className="font-medium">{String(value)}</span>
        </span>
      ))}
    </div>
  )
}
