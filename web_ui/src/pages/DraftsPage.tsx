/**
 * Drafts queue — every classified, follow-up-worthy feedback has a draft;
 * support staff pick one, read it, copy it, send it from their own tool.
 *
 * Layout choice: card grid rather than a tight table, because the body
 * preview is what the reviewer is actually evaluating — the metadata
 * lives in chips on top of each card. 200-char preview leaves enough
 * room to judge tone without making the card huge.
 */
import { useState } from 'react'
import { useDrafts } from '@/api/client'
import { useFilters } from '@/hooks/useFilters'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChannelBadge, PlatformBadge } from '@/components/SeverityBadge'
import { DraftDetailPanel } from '@/components/DraftDetailPanel'
import { formatRelative } from '@/lib/format'

export default function DraftsPage() {
  const { filters } = useFilters()
  const [selectedDraftId, setSelectedDraftId] = useState<string | null>(null)

  const { data, isLoading, error } = useDrafts({
    app: filters.app,
    platform: filters.platform,
    channel: filters.channel,
    limit: 100,
  })

  return (
    <div className="p-6">
      <div className="mb-4 flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">Drafts</h2>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.length} pending draft${data.length === 1 ? '' : 's'}` : ''}
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-destructive">Error: {String(error)}</p>}

      {data && data.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No drafts match the current filters.
        </p>
      )}

      {data && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.map((draft) => (
            <Card key={draft.id} className="flex h-full flex-col">
              <CardContent className="flex flex-1 flex-col gap-2 pt-4">
                <div className="flex flex-wrap items-center gap-1 text-xs">
                  <ChannelBadge channel={draft.channel} />
                  <PlatformBadge platform={draft.platform} />
                  <Badge variant="outline" className="uppercase">
                    {draft.app_slug}
                  </Badge>
                  <Badge variant="outline">{draft.language_code}</Badge>
                  <Badge
                    className={
                      draft.status === 'sent'
                        ? 'bg-emerald-500 text-white hover:bg-emerald-500'
                        : 'bg-slate-500 text-white hover:bg-slate-500'
                    }
                  >
                    {draft.status}
                  </Badge>
                </div>

                <p className="line-clamp-5 flex-1 whitespace-pre-wrap text-sm">
                  {draft.body_preview}
                </p>

                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>
                    {draft.citation_count} citation
                    {draft.citation_count === 1 ? '' : 's'} ·{' '}
                    {formatRelative(draft.generated_at)}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => setSelectedDraftId(draft.id)}
                  >
                    Open
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <DraftDetailPanel
        draftId={selectedDraftId}
        onClose={() => setSelectedDraftId(null)}
      />
    </div>
  )
}
