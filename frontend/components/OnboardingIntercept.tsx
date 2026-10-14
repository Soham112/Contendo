'use client'

import { useState, useEffect } from 'react'
import { motion } from 'motion/react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogActions } from '@/components/ui/dialog'
import { Input } from '@/components/ui/field'
import { riseIn, transition } from '@/components/ui/motion'
import { ErrorState } from '@/components/ui/states'
import { chipClass } from '@/components/ui/chip'
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
  const [saveError, setSaveError] = useState('')

  // animation state
  const [entered, setEntered] = useState(false)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    const id = requestAnimationFrame(() => setEntered(true))
    return () => cancelAnimationFrame(id)
  }, [])

  const q = QUESTIONS[step]
  const isLast = step === QUESTIONS.length - 1
  const currentChipAnswer = q.type === 'chip' ? chipAnswers[step] : null

  function selectChip(chip: string) {
    setChipAnswers(prev => prev.map((v, i) => (i === step ? (v === chip ? null : chip) : v)))
  }

  async function finish(finalChipAnswers: (string | null)[], finalText: string | null) {
    setSaving(true)
    setSaveError('')
    try {
      const res = await api.getProfile()
      if (!res.ok) throw new Error('Profile check failed')
      const existing: ProfileData = (await res.json()).profile ?? {}
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

      await api.saveProfile({ ...merged, voice_questionnaire_completed: true })
      await api.recordOnboardingStep('enhancement', 'completed')
    } catch (err) {
      console.error('[OnboardingIntercept] profile save error:', err)
      setSaveError('We couldn’t save your voice answers. Please try again.')
      return
    } finally {
      setSaving(false)
    }

    localStorage.setItem('contendo_intercept_done', '1')
    setExiting(true)
    await new Promise<void>(resolve => setTimeout(resolve, 150))
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
    <Dialog
      open={entered && !exiting}
      onOpenChange={(open) => { if (!open && !saving) void finish(chipAnswers, null) }}
      title="A few questions about your voice"
      description={`Question ${step + 1} of ${QUESTIONS.length}. Every question is optional.`}
    >
      {saveError && <div className="mb-4"><ErrorState message={saveError} /></div>}
      <div aria-hidden="true" className="mb-6 flex items-center gap-2">
        {QUESTIONS.map((_, i) => (
          <span key={i} className={`h-1.5 flex-1 rounded-full transition-colors duration-200 ${i <= step ? 'bg-primary' : 'bg-surface-container-high'}`} />
        ))}
      </div>

      {/* Each question fades and rises in. */}
      <motion.div key={step} initial={riseIn.initial} animate={riseIn.animate} transition={transition.base}>
        {q.type === 'chip' ? (
          <fieldset>
            <legend className="font-headline italic text-[1.3rem] leading-snug text-on-surface mb-6">{q.headline}</legend>
            <div className="flex flex-wrap gap-2">
              {q.chips.map(chip => (
                <button
                  key={chip}
                  type="button"
                  aria-pressed={currentChipAnswer === chip}
                  onClick={() => selectChip(chip)}
                  className={chipClass(currentChipAnswer === chip)}
                >
                  {chip}
                </button>
              ))}
            </div>
          </fieldset>
        ) : (
          <div>
            <label htmlFor="voice-answer" className="block font-headline italic text-[1.3rem] leading-snug text-on-surface mb-6">{q.headline}</label>
            <Input
              id="voice-answer"
              value={textValue}
              onChange={e => setTextValue(e.target.value)}
              placeholder={q.placeholder}
              autoFocus
              onKeyDown={e => { if (e.key === 'Enter' && !saving) handleNext() }}
            />
          </div>
        )}
      </motion.div>

      <DialogActions>
        <Button variant="tertiary" onClick={handleSkip} disabled={saving}>Skip</Button>
        <Button onClick={handleNext} loading={saving} disabled={!canAdvance} disabledReason="Choose an answer to continue">
          {isLast ? 'Done' : 'Next'}
        </Button>
      </DialogActions>
    </Dialog>
  )
}
