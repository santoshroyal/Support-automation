/**
 * Spikes — clusters that crossed the volume threshold inside their
 * recent window. Two sections: Active (red bordered, last 24 h) and
 * Historical. Click a spike to see the sample feedbacks the system
 * captured at detection time.
 *
 * We don't ship the cluster's full membership here in phase 1 —
 * `sample_feedback_ids` (5 representative items per spike) is what the
 * API returns. If support staff ask for the whole cluster, the next
 * iteration is a /api/clusters/{id}/feedbacks endpoint.
 */
import { useState } from 'react'
import { useSpikeFeedbacks, useSpikes } from '@/api/client'
import { useFilters } from '@/hooks/useFilters'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  ChannelBadge,
  PlatformBadge,
} from '@/components/SeverityBadge'
import { cn } from '@/lib/utils'
import { formatDateTime, formatRelative } from '@/lib/format'

export default function SpikesPage() {
  const { filters } = useFilters()
  const [selectedSpikeId, setSelectedSpikeId] = useState<string | null>(null)

  const { data, isLoading, error } = useSpikes({
    app: filters.app,
    limit: 100,
  })

  const active = (data ?? []).filter((spike) => spike.is_active)
  const historical = (data ?? []).filter((spike) => !spike.is_active)

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">Spikes</h2>
        <p className="text-xs text-muted-foreground">
          {data ? `${active.length} active, ${historical.length} historical` : ''}
        </p>
      </div>

      {isLoading && <p className="text-muted-foreground">Loading…</p>}
      {error && <p className="text-destructive">Error: {String(error)}</p>}

      <Section
        label={`Active (last 24h) · ${active.length}`}
        spikes={active}
        accent="active"
        onOpen={setSelectedSpikeId}
      />
      <Section
        label={`Historical · ${historical.length}`}
        spikes={historical}
        accent="historical"
        onOpen={setSelectedSpikeId}
      />

      <SpikeFeedbacksDialog
        spikeId={selectedSpikeId}
        onClose={() => setSelectedSpikeId(null)}
      />
    </div>
  )
}

type SectionProps = {
  label: string
  spikes: ReturnType<typeof useSpikes>['data'] extends infer T
    ? T extends Array<infer Item>
      ? Item[]
      : never
    : never
  accent: 'active' | 'historical'
  onOpen: (id: string) => void
}

function Section({ label, spikes, accent, onOpen }: SectionProps) {
  if (spikes.length === 0) {
    return (
      <section>
        <h3 className="text-xs font-semibold uppercase text-muted-foreground">
          {label}
        </h3>
        <p className="mt-2 text-sm text-muted-foreground">None.</p>
      </section>
    )
  }
  return (
    <section>
      <h3 className="text-xs font-semibold uppercase text-muted-foreground">
        {label}
      </h3>
      <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        {spikes.map((spike) => (
          <Card
            key={spike.id}
            className={cn(
              'border-2',
              accent === 'active'
                ? 'border-red-500/60'
                : 'border-border',
            )}
          >
            <CardContent className="pt-4">
              <div className="flex flex-wrap items-center gap-1 text-xs">
                <Badge
                  className={cn(
                    accent === 'active'
                      ? 'bg-red-500 text-white hover:bg-red-500'
                      : 'bg-slate-500 text-white hover:bg-slate-500',
                  )}
                >
                  {accent === 'active' ? 'active' : 'historical'}
                </Badge>
                <span className="text-muted-foreground">
                  ratio ×{spike.ratio.toFixed(1)}
                </span>
              </div>

              <p className="mt-2 line-clamp-3 text-sm font-medium">
                {spike.cluster_label ?? '(no cluster label)'}
              </p>

              <dl className="mt-3 grid grid-cols-2 gap-2 text-xs text-muted-foreground">
                <div>
                  <dt>Count</dt>
                  <dd className="text-base font-semibold text-foreground">
                    {spike.count}
                  </dd>
                </div>
                <div>
                  <dt>Baseline</dt>
                  <dd className="text-base font-semibold text-foreground">
                    {spike.baseline.toFixed(1)}/day
                  </dd>
                </div>
              </dl>

              <div className="mt-3 flex items-center justify-between text-xs text-muted-foreground">
                <span>{formatRelative(spike.window_end)}</span>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onOpen(spike.id)}
                >
                  Drill down
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </section>
  )
}

function SpikeFeedbacksDialog({
  spikeId,
  onClose,
}: {
  spikeId: string | null
  onClose: () => void
}) {
  const { data, isLoading } = useSpikeFeedbacks(spikeId)
  return (
    <Dialog open={Boolean(spikeId)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Sample feedbacks for this spike</DialogTitle>
        </DialogHeader>
        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {data && (
          <ScrollArea className="max-h-[70vh] pr-3">
            <ul className="space-y-2">
              {(data.feedbacks ?? []).map((feedback) => (
                <li key={feedback.id} className="rounded border bg-background p-3">
                  <div className="flex flex-wrap items-center gap-1 text-xs">
                    <ChannelBadge channel={feedback.channel} />
                    <PlatformBadge platform={feedback.platform} />
                    <span className="text-muted-foreground">
                      {feedback.app_slug} · {feedback.author_identifier}
                    </span>
                    <span className="ml-auto text-muted-foreground">
                      {formatDateTime(feedback.received_at)}
                    </span>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm">
                    {feedback.raw_text_preview}
                  </p>
                </li>
              ))}
              {(data.feedbacks ?? []).length === 0 && (
                <li className="text-sm text-muted-foreground">
                  No sample feedbacks recorded on this spike.
                </li>
              )}
            </ul>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
