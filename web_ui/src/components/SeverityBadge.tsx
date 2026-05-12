/** Colour-coded severity / sentiment / status pills used across pages. */
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const SEVERITY_CLASS: Record<string, string> = {
  critical: 'bg-red-600 text-white hover:bg-red-600',
  high: 'bg-red-500 text-white hover:bg-red-500',
  medium: 'bg-amber-500 text-white hover:bg-amber-500',
  low: 'bg-slate-400 text-white hover:bg-slate-400',
}

export function SeverityBadge({ severity }: { severity?: string | null }) {
  if (!severity) return <Badge variant="outline">unclassified</Badge>
  return (
    <Badge className={cn('uppercase', SEVERITY_CLASS[severity] ?? 'bg-slate-500 text-white')}>
      {severity}
    </Badge>
  )
}

const SENTIMENT_CLASS: Record<string, string> = {
  positive: 'bg-emerald-500 text-white hover:bg-emerald-500',
  neutral: 'bg-slate-400 text-white hover:bg-slate-400',
  negative: 'bg-red-500 text-white hover:bg-red-500',
}

export function SentimentBadge({ sentiment }: { sentiment?: string | null }) {
  if (!sentiment) return null
  return (
    <Badge className={cn('uppercase', SENTIMENT_CLASS[sentiment] ?? 'bg-slate-500')}>
      {sentiment}
    </Badge>
  )
}

export function ChannelBadge({ channel }: { channel: string }) {
  return <Badge variant="secondary">{channel}</Badge>
}

export function PlatformBadge({ platform }: { platform: string }) {
  return <Badge variant="outline">{platform}</Badge>
}
