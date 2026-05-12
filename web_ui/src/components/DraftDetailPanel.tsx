/**
 * Full draft view in a dialog: the customer-facing body on the left, the
 * citation list (support-staff only) on the right, and the original
 * feedback at the bottom for context.
 */
import { useState } from 'react'
import { useDraftDetail } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  ChannelBadge,
  PlatformBadge,
  SeverityBadge,
} from '@/components/SeverityBadge'
import { formatDateTime } from '@/lib/format'

type Props = {
  draftId: string | null
  onClose: () => void
}

export function DraftDetailPanel({ draftId, onClose }: Props) {
  const { data, isLoading, error } = useDraftDetail(draftId)
  const [copied, setCopied] = useState(false)

  async function copyBody() {
    if (!data) return
    await navigator.clipboard.writeText(data.body)
    setCopied(true)
    setTimeout(() => setCopied(false), 1500)
  }

  return (
    <Dialog open={Boolean(draftId)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle>Draft reply</DialogTitle>
          <DialogDescription>
            Review and copy. Sending happens in the support team's own
            tool (Gmail or store console) — this dashboard is read-only.
          </DialogDescription>
        </DialogHeader>
        {isLoading && (
          <p className="text-sm text-muted-foreground">Loading…</p>
        )}
        {error && (
          <p className="text-sm text-destructive">Error: {String(error)}</p>
        )}
        {data && (
          <ScrollArea className="max-h-[70vh] pr-3">
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <ChannelBadge channel={data.channel} />
                <PlatformBadge platform={data.platform} />
                <span className="text-muted-foreground">
                  {data.app_slug} · language {data.language_code} · status{' '}
                  {data.status}
                </span>
                <span className="ml-auto text-muted-foreground">
                  generated {formatDateTime(data.generated_at)}
                </span>
              </div>

              <section className="grid grid-cols-1 gap-4 md:grid-cols-[2fr_1fr]">
                <div>
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                      Customer-facing reply
                    </h3>
                    <Button size="sm" variant="outline" onClick={copyBody}>
                      {copied ? 'Copied!' : 'Copy draft'}
                    </Button>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                    {data.body}
                  </p>
                </div>

                <div>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                    Citations ({(data.citations ?? []).length})
                  </h3>
                  <p className="text-[11px] text-muted-foreground">
                    Internal — not shown to the user.
                  </p>
                  {(data.citations ?? []).length === 0 && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      (no citations recorded)
                    </p>
                  )}
                  <ul className="mt-2 space-y-2 text-xs">
                    {(data.citations ?? []).map((citation) => (
                      <li
                        key={citation.knowledge_chunk_id}
                        className="rounded border bg-background p-2"
                      >
                        <div className="font-medium">
                          {citation.source_url ? (
                            <a
                              href={citation.source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-primary underline"
                            >
                              {citation.source_title}
                            </a>
                          ) : (
                            citation.source_title
                          )}
                        </div>
                        <div className="mt-1 text-muted-foreground">
                          {citation.snippet}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              </section>

              <Separator />

              <section>
                <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                  Original feedback from {data.original_feedback_author}
                </h3>
                <p className="mt-1 whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                  {data.original_feedback_text}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Received {formatDateTime(data.original_feedback_received_at)}
                </p>
              </section>

              {data.classification && (
                <section>
                  <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                    Classification
                  </h3>
                  <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                    <SeverityBadge severity={data.classification.severity} />
                    <span>{data.classification.category}</span>
                    {data.classification.sub_category && (
                      <span className="text-muted-foreground">
                        / {data.classification.sub_category}
                      </span>
                    )}
                  </div>
                </section>
              )}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
