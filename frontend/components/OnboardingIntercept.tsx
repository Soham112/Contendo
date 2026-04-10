'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useApi } from '@/lib/api'
import type { ProfileData } from '@/lib/api'

// ── Question definitions ──────────────────────────────────────────────────────

type ProfileListField = 'voice_descriptors' | 'writing_rules' | 'opinions'
type ProfileScalarField = 'target_audience'
type ProfileField = ProfileListField | ProfileScalarField

interface ChipQuestion {
  type: 'chip'
  headline: string
  field: ProfileField
  chips: string[]
  valueTransform?: (val: string) => string
}

interface TextQuestion {
  type: 'text'
  headline: string
  field: 'opinions'
  placeholder: string
}

type Question = ChipQuestion | TextQuestion

const QUESTIONS: Question[] = [
  {
    type: 'chip',
    headline: "When you explain something complex, you usually...",
    field: 'voice_descriptors',
    chips: ["Get to the point fast", "Build context first", "Use analogies", "Lead with data"],
  },
  {
    type: 'chip',
    headline: "Your natural writing mode is...",
    field: 'voice_descriptors',
    chips: ["Teaching something", "Sharing a strong opinion", "Telling a story", "Challenging a myth"],
  },
  {
    type: 'chip',
    headline: "The people you're writing for are mostly...",
    field: 'target_audience',
    chips: ["Peers in my field", "People I'm trying to convince", "People newer than me", "A mix"],
  },
  {
    type: 'chip',
    headline: "After reading your post, you want people to...",
    field: 'writing_rules',
    chips: ["Learn something new", "See something differently", "Try what you recommend", "Think you're worth following"],
    valueTransform: (val) => `My goal: ${val}`,
  },
  {
    type: 'text',
    headline: "What's one thing people in your field get wrong?",
    field: 'opinions',
    placeholder: "e.g. Most people optimize the wrong thing",
  },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function mergeUnique(existing: string[], additions: string[]): string[] {
  const lower = new Set(existing.map(s => s.toLowerCase()))
  return [
    ...existing,
    ...additions.filter(s => s.trim() && !lower.has(s.toLowerCase())),
  ]
}

// ── Component ─────────────────────────────────────────────────────────────────

interface OnboardingInterceptProps {
  destination: string
  onComplete?: () => void
}

export default function OnboardingIntercept({ destination, onComplete }: OnboardingInterceptProps) {
  const api = useApi()
  const router = useRouter()

  const [step, setStep] = useState(0)
  // chip answers indexed by question index; null = not answered
  const [chipAnswers, setChipAnswers] = useState<(string | null)[]>(
    Array(QUESTIONS.length).fill(null)
  )
  const [textValue, setTextValue] = useState('')
  const [saving, setSaving] = useState(false)

  const q = QUESTIONS[step]
  const isLast = step === QUESTIONS.length - 1
  const currentChipAnswer = q.type === 'chip' ? chipAnswers[step] : null

  function selectChip(chip: string) {
    setChipAnswers(prev => prev.map((v, i) => (i === step ? (v === chip ? null : chip) : v)))
  }

  async function finish(finalChipAnswers: (string | null)[], finalText: string | null) {
    setSaving(true)
    try {
      const res = await api.getProfile()
      const existing: ProfileData = res.ok ? (await res.json()).profile ?? {} : {}
      const merged: ProfileData = { ...existing }

      QUESTIONS.forEach((question, i) => {
        const isTextQ = question.type === 'text'
        const rawVal = isTextQ ? finalText : finalChipAnswers[i]
        if (!rawVal?.trim()) return

        let val = rawVal.trim()
        if (question.type === 'chip' && question.valueTransform) {
          val = question.valueTransform(val)
        }

        if (question.field === 'target_audience') {
          if (!merged.target_audience) merged.target_audience = val
        } else {
          const field = question.field as ProfileListField
          const current = (merged[field] as string[] | undefined) ?? []
          merged[field] = mergeUnique(current, [val])
        }
      })

      await api.saveProfile(merged)
    } catch (err) {
      console.error('[OnboardingIntercept] profile save error:', err)
    } finally {
      setSaving(false)
    }

    localStorage.setItem('contendo_intercept_done', '1')
    onComplete?.()
    router.push(destination)
  }

  async function handleNext() {
    if (saving) return
    const textVal = q.type === 'text' ? (textValue.trim() || null) : null

    if (isLast) {
      await finish(chipAnswers, textVal)
    } else {
      setStep(s => s + 1)
      setTextValue('')
    }
  }

  async function handleSkip() {
    if (saving) return
    // Clear any selection for this step
    const cleared = chipAnswers.map((v, i) => (i === step ? null : v))
    setChipAnswers(cleared)

    if (isLast) {
      await finish(cleared, null)
    } else {
      setStep(s => s + 1)
      setTextValue('')
    }
  }

  const canAdvance = q.type === 'chip' ? !!currentChipAnswer : true

  return (
    <div className="min-h-screen bg-[#faf9f8] flex items-center justify-center px-4">
      <div
        className="w-full max-w-lg bg-white rounded-2xl px-10 py-12"
        style={{
          boxShadow:
            '0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)',
        }}
      >
        {/* Progress dots */}
        <div className="flex items-center gap-2 justify-center mb-10">
          {QUESTIONS.map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full transition-all duration-200 ${
                i <= step
                  ? 'bg-[#58614f]'
                  : 'border border-[#58614f] opacity-30'
              }`}
            />
          ))}
        </div>

        {/* Headline */}
        <h2 className="font-headline italic text-[1.3rem] text-[#2f3333] mb-8 leading-snug text-center">
          {q.headline}
        </h2>

        {/* Input area */}
        {q.type === 'chip' ? (
          <div className="flex flex-wrap gap-2.5 justify-center mb-10">
            {q.chips.map(chip => (
              <button
                key={chip}
                onClick={() => selectChip(chip)}
                className={`px-4 py-2 rounded-full text-[13px] transition-all duration-150 ${
                  currentChipAnswer === chip
                    ? 'bg-[#58614f] text-white'
                    : 'bg-[#f3f4f3] text-[#2f3333] hover:bg-[#edeeed]'
                }`}
              >
                {chip}
              </button>
            ))}
          </div>
        ) : (
          <div className="mb-10">
            <input
              type="text"
              value={textValue}
              onChange={e => setTextValue(e.target.value)}
              placeholder={q.placeholder}
              autoFocus
              className="w-full bg-[#f3f4f3] rounded-xl px-4 py-3 text-[14px] text-[#2f3333] placeholder-[#2f3333]/40 outline-none focus:bg-[#edeeed] transition-colors"
              onKeyDown={e => {
                if (e.key === 'Enter' && !saving) handleNext()
              }}
            />
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-end gap-4">
          <button
            onClick={handleSkip}
            disabled={saving}
            className="text-[12px] text-[#2f3333]/40 hover:text-[#2f3333]/60 transition-colors disabled:opacity-40"
          >
            {isLast && q.type === 'text' ? 'Skip this one →' : 'Skip'}
          </button>

          <button
            onClick={handleNext}
            disabled={!canAdvance || saving}
            className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
          >
            {saving ? 'Saving...' : isLast ? 'Done →' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  )
}
