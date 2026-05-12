/**
 * Side-by-side detail view: full feedback + classification + draft body
 * + citations. Rendered as a shadcn Dialog so it works as a focused
 * lightbox over the table without needing a separate route.
 */
import { useFeedbackDetail } from '@/api/client'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Separator } from '@/components/ui/separator'
import {
  ChannelBadge,
  PlatformBadge,
  SentimentBadge,
  SeverityBadge,
} from '@/components/SeverityBadge'
import { formatDateTime } from '@/lib/format'

type Props = {
  feedbackId: string | null
  onClose: () => void
}

export function FeedbackDetailPanel({ feedbackId, onClose }: Props) {
  const { data, isLoading, error } = useFeedbackDetail(feedbackId)

  return (
    <Dialog open={Boolean(feedbackId)} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Feedback detail</DialogTitle>
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
                  {data.app_slug} · {data.author_identifier}
                </span>
                <span className="ml-auto text-muted-foreground">
                  {formatDateTime(data.received_at)}
                </span>
              </div>

              <section>
                <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                  Original text
                </h3>
                <p className="mt-1 whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                  {data.raw_text}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Device: {data.device_info ?? '—'} · App version:{' '}
                  {data.app_version ?? '—'} · Language:{' '}
                  {data.language_code ?? '—'}
                </p>
              </section>

              {data.classification && (
                <>
                  <Separator />
                  <section>
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                      Classification
                    </h3>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-sm">
                      <SeverityBadge severity={data.classification.severity} />
                      <SentimentBadge
                        sentiment={data.classification.sentiment}
                      />
                      <span className="text-foreground">
                        {data.classification.category}
                      </span>
                      {data.classification.sub_category && (
                        <span className="text-muted-foreground">
                          / {data.classification.sub_category}
                        </span>
                      )}
                      <span className="ml-auto text-xs text-muted-foreground">
                        by {data.classification.language_model_used}
                      </span>
                    </div>
                    {data.classification.requires_followup && (
                      <p className="mt-1 text-xs text-amber-600">
                        Marked as requiring follow-up
                      </p>
                    )}
                  </section>
                </>
              )}

              {data.draft && (
                <>
                  <Separator />
                  <section>
                    <h3 className="text-xs font-semibold uppercase text-muted-foreground">
                      Draft reply ({data.draft.status})
                    </h3>
                    <p className="mt-1 whitespace-pre-wrap rounded-md border bg-muted/40 p-3 text-sm">
                      {data.draft.body}
                    </p>
                    {(data.draft.citations ?? []).length > 0 && (
                      <details className="mt-2 text-xs">
                        <summary className="cursor-pointer text-muted-foreground">
                          {(data.draft.citations ?? []).length} citation
                          {(data.draft.citations ?? []).length === 1 ? '' : 's'} (for
                          support-staff verification)
                        </summary>
                        <ul className="mt-2 space-y-2">
                          {(data.draft.citations ?? []).map((citation) => (
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
                      </details>
                    )}
                  </section>
                </>
              )}
            </div>
          </ScrollArea>
        )}
      </DialogContent>
    </Dialog>
  )
}
