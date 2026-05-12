/**
 * Inbox — the system's queue of user feedback.
 *
 * Renders a table of feedback rows filtered by the shared FilterBar state.
 * Clicking a row opens the FeedbackDetailPanel (dialog) with the full
 * classification + draft + citations, so the support team can scan and
 * drill in without leaving the page.
 */
import { useState } from 'react'
import { useFeedbackList } from '@/api/client'
import { useFilters } from '@/hooks/useFilters'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import {
  ChannelBadge,
  PlatformBadge,
} from '@/components/SeverityBadge'
import { FeedbackDetailPanel } from '@/components/FeedbackDetailPanel'
import { Badge } from '@/components/ui/badge'
import { formatRelative } from '@/lib/format'

export default function InboxPage() {
  const { filters } = useFilters()
  const [selectedId, setSelectedId] = useState<string | null>(null)

  const { data, isLoading, error } = useFeedbackList({
    app: filters.app,
    platform: filters.platform,
    channel: filters.channel,
    limit: 100,
  })

  return (
    <div className="p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">Inbox</h2>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.length} feedback${data.length === 1 ? '' : 's'}` : ''}
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-destructive">Error: {String(error)}</p>}

      {data && (
        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>App</TableHead>
                <TableHead>Channel / Platform</TableHead>
                <TableHead>Author</TableHead>
                <TableHead>Feedback</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Received</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row) => (
                <TableRow
                  key={row.id}
                  className="cursor-pointer"
                  onClick={() => setSelectedId(row.id)}
                >
                  <TableCell className="font-medium uppercase">
                    {row.app_slug}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1">
                      <ChannelBadge channel={row.channel} />
                      <PlatformBadge platform={row.platform} />
                    </div>
                  </TableCell>
                  <TableCell className="text-sm">
                    {row.author_identifier}
                  </TableCell>
                  <TableCell className="max-w-[36rem] text-sm">
                    {row.raw_text_preview}
                  </TableCell>
                  <TableCell>
                    <div className="flex flex-wrap items-center gap-1">
                      {row.has_classification ? (
                        <Badge variant="outline" className="text-xs">
                          classified
                        </Badge>
                      ) : (
                        <Badge variant="outline" className="text-xs text-muted-foreground">
                          unclassified
                        </Badge>
                      )}
                      {row.has_draft && (
                        <Badge className="bg-emerald-500 text-white hover:bg-emerald-500 text-xs">
                          draft
                        </Badge>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {formatRelative(row.received_at)}
                  </TableCell>
                </TableRow>
              ))}
              {data.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-muted-foreground">
                    No feedback matches the current filters.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      )}

      <FeedbackDetailPanel
        feedbackId={selectedId}
        onClose={() => setSelectedId(null)}
      />
    </div>
  )
}
