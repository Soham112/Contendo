'use client'

import { useState, useEffect, useRef } from 'react'
import { useUser, useSignIn } from '@clerk/nextjs'
import { useRouter, useSearchParams } from 'next/navigation'
import { Sparkles } from 'lucide-react'
import { useApi } from '@/lib/api'
import {
  ROLE_OPTIONS,
  ROLE_TO_BUCKET,
  OPINION_STATEMENTS,
  EXPERIENCE_OPTIONS,
  EXPERIENCE_PLACEHOLDER,
  CORE_AUDIENCE_PILLS,
  ROLE_AUDIENCE_PILLS,
  type RoleKey,
} from '@/lib/first-post-constants'
import OnboardingIntercept from '@/components/OnboardingIntercept'

// ── Types ─────────────────────────────────────────────────────────────────────
interface Answers {
  role: string
  roleLabel: string
  topic: string
  format: string
  experienceType: string
  experienceDetail: string
  opinion: string
  opinionIsCustom: boolean
  audience: string
  voiceSample: string
}

interface DraftState {
  post: string
  score: number
  archetype: string
  postId: number | null
}

// Fields extracted from resume or fallback questions
interface ExtractedProfile {
  name?: string | null
  role?: string | null
  bio?: string | null
  location?: string | null
  topics_of_expertise?: string[]
  voice_descriptors?: string[]
  opinions?: string[]
  writing_samples?: string[]
}

const WELCOME_TOPIC_PREFILL_KEY = 'contendo_topic'

// ── SVG icons for role tiles ──────────────────────────────────────────────────
function IconDataMl() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="5" y="5" width="10" height="10" rx="1.5" />
      <line x1="8" y1="2" x2="8" y2="5" />
      <line x1="12" y1="2" x2="12" y2="5" />
      <line x1="8" y1="15" x2="8" y2="18" />
      <line x1="12" y1="15" x2="12" y2="18" />
      <line x1="2" y1="8" x2="5" y2="8" />
      <line x1="2" y1="12" x2="5" y2="12" />
      <line x1="15" y1="8" x2="18" y2="8" />
      <line x1="15" y1="12" x2="18" y2="12" />
    </svg>
  )
}

function IconDataEng() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="4" cy="10" r="2" />
      <circle cx="10" cy="10" r="2" />
      <circle cx="16" cy="10" r="2" />
      <line x1="6" y1="10" x2="8" y2="10" />
      <line x1="12" y1="10" x2="14" y2="10" />
    </svg>
  )
}

function IconProduct() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="3" y="3" width="6" height="6" rx="1" />
      <rect x="11" y="3" width="6" height="6" rx="1" />
      <rect x="3" y="11" width="6" height="6" rx="1" />
      <rect x="11" y="11" width="6" height="6" rx="1" />
    </svg>
  )
}

function IconSoftware() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M7 6L3 10l4 4" />
      <path d="M13 6l4 4-4 4" />
      <path d="M11 5l-2 10" />
    </svg>
  )
}

function IconDesign() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 16l3.5-3.5L14 6l2-2 1 1-2 2-6.5 6.5L5 17z" />
      <path d="M13 5l2 2" />
    </svg>
  )
}

function IconFounder() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 4v12M5 9l5-5 5 5" />
    </svg>
  )
}

function IconMarketer() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3,14 7,9 10,12 16,5" />
      <polyline points="13,5 16,5 16,8" />
    </svg>
  )
}

function IconConsultant() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M10 3a5 5 0 0 1 3.5 8.5c-.6.6-.5 1.3-.5 1.5H7c0-.2.1-.9-.5-1.5A5 5 0 0 1 10 3z" />
      <line x1="7.5" y1="15.5" x2="12.5" y2="15.5" />
      <line x1="8.5" y1="17.5" x2="11.5" y2="17.5" />
    </svg>
  )
}

function IconOther() {
  return (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="currentColor">
      <circle cx="5" cy="10" r="1.5" />
      <circle cx="10" cy="10" r="1.5" />
      <circle cx="15" cy="10" r="1.5" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 8l3.5 3.5L13 4" />
    </svg>
  )
}

function GoogleIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <path d="M15.68 8.18c0-.57-.05-1.11-.14-1.64H8v3.1h4.3a3.67 3.67 0 0 1-1.6 2.41v2h2.58c1.51-1.39 2.38-3.44 2.38-5.87z" fill="#4285F4" />
      <path d="M8 16c2.16 0 3.97-.72 5.3-1.94l-2.58-2a4.78 4.78 0 0 1-2.72.75c-2.09 0-3.86-1.41-4.5-3.31H.84v2.07A8 8 0 0 0 8 16z" fill="#34A853" />
      <path d="M3.5 9.5A4.8 4.8 0 0 1 3.25 8c0-.52.09-1.03.25-1.5V4.43H.84A8 8 0 0 0 0 8c0 1.29.31 2.51.84 3.57L3.5 9.5z" fill="#FBBC05" />
      <path d="M8 3.19c1.18 0 2.24.41 3.07 1.2L13.35 2.1A8 8 0 0 0 8 0 8 8 0 0 0 .84 4.43L3.5 6.5C4.14 4.6 5.91 3.19 8 3.19z" fill="#EA4335" />
    </svg>
  )
}

// ── Upload drop zone (reused in Step 6 and Profile Gate) ──────────────────────
function ResumeDropZone({
  resumeFile,
  isDragging,
  uploading,
  onFile,
  onDragOver,
  onDragLeave,
  onDrop,
  fileInputRef,
}: {
  resumeFile: File | null
  isDragging: boolean
  uploading: boolean
  onFile: (f: File) => void
  onDragOver: (e: React.DragEvent) => void
  onDragLeave: (e: React.DragEvent) => void
  onDrop: (e: React.DragEvent) => void
  fileInputRef: React.RefObject<HTMLInputElement>
}) {
  return (
    <>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        className="hidden"
        onChange={e => {
          const f = e.target.files?.[0]
          if (f) onFile(f)
        }}
      />
      <div
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onDrop={onDrop}
        onClick={() => !uploading && fileInputRef.current?.click()}
        className={`rounded-2xl p-8 text-center cursor-pointer transition-all duration-150 ${
          isDragging
            ? 'bg-[#edeeed]'
            : 'bg-[#f3f4f3] hover:bg-[#edeeed]'
        }`}
        style={{
          border: `2px dashed rgba(174, 179, 178, ${isDragging ? '0.5' : '0.25'})`,
        }}
      >
        {uploading ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-5 h-5 border-2 border-[#58614f]/30 border-t-[#58614f] rounded-full animate-spin" />
            <p className="text-[13px] text-[#645e57]">Reading your resume...</p>
          </div>
        ) : resumeFile ? (
          <div className="flex items-center justify-center gap-2">
            <span className="text-[#58614f]"><CheckIcon /></span>
            <span className="text-[14px] text-[#2f3333] font-medium">{resumeFile.name}</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#aeb3b2" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="12" y1="18" x2="12" y2="12" />
              <line x1="9" y1="15" x2="15" y2="15" />
            </svg>
            <p className="text-[13px] text-[#645e57]">
              Drag &amp; drop your resume here, or <span className="text-[#58614f]">browse</span>
            </p>
            <p className="text-[11px] text-[#aeb3b2]">PDF only</p>
          </div>
        )}
      </div>
    </>
  )
}

const ROLE_ICONS: Record<RoleKey, React.ReactNode> = {
  data_ml:    <IconDataMl />,
  data_eng:   <IconDataEng />,
  product:    <IconProduct />,
  software:   <IconSoftware />,
  design:     <IconDesign />,
  founder:    <IconFounder />,
  marketer:   <IconMarketer />,
  consultant: <IconConsultant />,
  other:      <IconOther />,
}

// ── Shared subcomponents ──────────────────────────────────────────────────────
function Wordmark() {
  return (
    <div className="flex flex-col items-center gap-1 mb-10">
      <span className="text-[28px] font-headline italic text-[#2f3333] tracking-tight">
        Contendo
      </span>
      <span className="text-[10px] uppercase tracking-[0.14em] text-[#645e57]">
        Editorial Atelier
      </span>
    </div>
  )
}

function StepDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`w-2 h-2 rounded-full transition-all duration-200 ${
            i <= current
              ? 'bg-[#58614f]'
              : 'border border-[#58614f] opacity-30'
          }`}
        />
      ))}
    </div>
  )
}

function buildContext(answers: Answers): string {
  const parts: string[] = []
  if (answers.experienceType) {
    parts.push(`Post should draw from: ${answers.experienceType}`)
  }
  if (answers.experienceDetail) {
    parts.push(`Specific context: ${answers.experienceDetail}`)
  }
  if (answers.opinion) {
    parts.push(`Core opinion/take: ${answers.opinion}`)
  }
  if (answers.audience) {
    parts.push(`Target audience: ${answers.audience}`)
  }
  return parts.join('\n')
}

// Deduplicate and merge string arrays, left-side wins on overlap
function mergeStringArrays(...arrays: (string[] | undefined | null)[]): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const arr of arrays) {
    for (const item of arr ?? []) {
      const key = item.trim().toLowerCase()
      if (key && !seen.has(key)) {
        seen.add(key)
        result.push(item.trim())
      }
    }
  }
  return result
}

// ── Generating screen ─────────────────────────────────────────────────────────
function GeneratingScreen() {
  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      <Wordmark />
      <div className="mt-8 text-center max-w-[420px]">
        <h2 className="font-headline text-[1.5rem] text-[#2f3333] leading-snug mb-3">
          Building your first post...
        </h2>
        <p className="text-[14px] text-[#645e57] mb-3">
          This usually takes 15–20 seconds.
        </p>
        <p className="text-[12px] text-[#2f3333]/50 leading-relaxed">
          This is built from what you just told us. Add sources after to make
          every post more specific to your expertise.
        </p>
      </div>
    </div>
  )
}

function GenerateErrorScreen({ onGoToWorkspace }: { onGoToWorkspace: () => void }) {
  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      <Wordmark />
      <div className="mt-8 text-center max-w-[460px]">
        <h2 className="font-headline text-[1.7rem] text-[#2f3333] leading-tight mb-3">
          Something went wrong.
        </h2>
        <p className="text-[14px] text-[#645e57] mb-8 leading-relaxed">
          We couldn&apos;t generate your post. You can try again from the workspace.
        </p>
        <button
          onClick={onGoToWorkspace}
          className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium"
        >
          Go to workspace →
        </button>
      </div>
    </div>
  )
}

// ── Draft screen ──────────────────────────────────────────────────────────────
function DraftScreen({
  topic,
  format,
  post,
  score,
  copied,
  onCopy,
  onFeedMemory,
  onCreate,
}: {
  topic: string
  format: string
  post: string
  score: number
  copied: boolean
  onCopy: () => void
  onFeedMemory: () => void
  onCreate: () => void
}) {
  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      <Wordmark />
      <div className="w-full max-w-[680px] bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-7 sm:px-9 py-8">
        <p className="label-caps text-[11px] text-[#645e57] mb-3">YOUR FIRST POST</p>

        <div className="flex flex-wrap gap-2 mb-3">
          <span className="px-2.5 py-1 rounded-full bg-[#edeeed] text-[11px] label-caps text-[#2f3333]">
            {format.toUpperCase()}
          </span>
          <span className="px-2.5 py-1 rounded-full bg-[#edeeed] text-[11px] label-caps text-[#2f3333]">
            CASUAL
          </span>
        </div>

        <p className="font-headline italic text-[1.1rem] text-[#2f3333]/65 mb-5 leading-relaxed">
          {topic}
        </p>

        <div className="sage-scrollbar bg-white rounded-xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] p-6 text-[1rem] leading-[1.7] text-[#2f3333] whitespace-pre-wrap max-h-[60vh] overflow-y-auto">
          {post}
        </div>

        {score > 0 && (
          <p className="mt-2 text-[12px] label-caps text-[#2f3333]/50">
            Authenticity score: {score}/100
          </p>
        )}

        <div className="mt-5 bg-[#f3f4f3] rounded-lg px-4 py-4 flex items-start gap-3">
          <Sparkles size={16} className="text-[#58614f] mt-[1px] shrink-0" />
          <p className="text-[13px] text-[#2f3333]/70 leading-relaxed">
            This post was built from what you just told us — no sources yet. Add
            articles, notes, and research to your memory and every future post
            will be grounded in your actual expertise.
          </p>
        </div>

        <div className="mt-5 flex justify-center">
          <button
            onClick={onCopy}
            className="px-4 py-1.5 rounded-full text-[11px] label-caps text-[#2f3333] ghost-border hover:bg-[#f3f4f3] transition-colors"
          >
            {copied ? 'Copied!' : 'Copy post'}
          </button>
        </div>

        <div className="mt-5 w-full max-w-[480px] mx-auto flex flex-col gap-2.5">
          <button
            onClick={onFeedMemory}
            className="btn-primary text-white py-2.5 rounded-xl text-[14px] font-medium w-full"
          >
            Add sources and improve →
          </button>
          <button
            onClick={onCreate}
            className="w-full py-2.5 rounded-xl text-[14px] text-[#2f3333] hover:bg-[#f3f4f3] transition-colors ghost-border"
          >
            Go to workspace →
          </button>
        </div>

        <p className="mt-3 text-center text-[11px] text-[#2f3333]/40">
          You can always find this post in History.
        </p>
      </div>
    </div>
  )
}

// ── Profile Gate (shown only when resumeSkipped=true and user clicks a CTA) ───
type GatePhase = 'choice' | 'upload' | 'fallback' | 'q1' | 'q2' | 'q3'

function ProfileGate({
  onDone,
  onSkip,
  api,
  onExtracted,
}: {
  onDone: () => void
  onSkip: () => void
  api: ReturnType<typeof useApi>
  onExtracted: (fields: ExtractedProfile) => Promise<void>
}) {
  const [phase, setPhase] = useState<GatePhase>('choice')
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Fallback Q&A state
  const [q1Answer, setQ1Answer] = useState('')
  const [q2Answer, setQ2Answer] = useState('')
  const [q3Answer, setQ3Answer] = useState('')
  const [savingFallback, setSavingFallback] = useState(false)

  const SENIORITY_OPTIONS = [
    'Just starting out',
    'Mid-level (3-6 years)',
    'Senior (7+ years)',
    'Leadership',
    'Founder',
  ]

  const DOMAIN_OPTIONS = [
    'Engineering',
    'Product',
    'Data & AI',
    'Design',
    'Marketing',
    'Finance',
    'Operations',
    'Other',
  ]

  function handleFile(f: File) {
    setResumeFile(f)
    setUploadError('')
  }

  async function handleUpload() {
    if (!resumeFile) return
    setUploading(true)
    setUploadError('')
    try {
      const res = await api.extractResume(resumeFile)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed.' }))
        throw new Error(err.detail ?? 'Upload failed.')
      }
      const extracted: ExtractedProfile = await res.json()
      await onExtracted(extracted)
      onDone()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed.'
      setUploadError(msg)
      setUploading(false)
    }
  }

  async function handleFallbackDone() {
    setSavingFallback(true)
    const fields: ExtractedProfile = {}
    if (q1Answer) {
      fields.bio = q1Answer
    }
    if (q2Answer) {
      fields.topics_of_expertise = [q2Answer]
    }
    if (q3Answer.trim()) {
      fields.writing_samples = [q3Answer.trim()]
    }
    await onExtracted(fields)
    onDone()
  }

  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      <Wordmark />

      <div className="w-full max-w-[520px] bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-8 py-10">

        {/* ── Choice ── */}
        {phase === 'choice' && (
          <div className="flex flex-col gap-6">
            <div>
              <h2 className="font-headline italic text-[2rem] text-[#2f3333] leading-tight mb-2">
                Before you go in
              </h2>
              <p className="text-[0.95rem] text-[#645e57] leading-relaxed">
                Your profile is almost empty right now. Posts will be generic
                until we know more about you.
              </p>
            </div>

            <div className="flex flex-col gap-4">
              {/* Option A */}
              <div className="flex flex-col gap-1.5">
                <button
                  onClick={() => setPhase('upload')}
                  className="btn-primary text-white py-3 rounded-2xl text-[14px] font-medium w-full"
                >
                  Upload your resume →
                </button>
                <p className="text-[12px] text-[#2f3333]/50 text-center">
                  Takes 10 seconds. We&apos;ll fill everything in.
                </p>
              </div>

              {/* Option B */}
              <div className="flex flex-col gap-1.5">
                <button
                  onClick={() => setPhase('q1')}
                  className="w-full py-3 rounded-2xl text-[14px] text-[#2f3333] bg-[#f3f4f3] hover:bg-[#edeeed] transition-colors"
                  style={{ border: '2px dashed rgba(174, 179, 178, 0.25)' }}
                >
                  Answer 3 quick questions instead →
                </button>
                <p className="text-[12px] text-[#2f3333]/50 text-center">
                  No resume? No problem. 45 seconds.
                </p>
              </div>

              {/* Option C */}
              <button
                onClick={onSkip}
                className="text-[12px] text-[#2f3333]/40 hover:text-[#2f3333]/60 transition-colors text-center w-full py-1"
              >
                Enter anyway — I&apos;ll improve my profile later
              </button>
            </div>
          </div>
        )}

        {/* ── Upload ── */}
        {phase === 'upload' && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="font-headline italic text-[1.75rem] text-[#2f3333] leading-tight mb-2">
                Upload your resume
              </h2>
              <p className="text-[0.9rem] text-[#645e57]">
                We&apos;ll extract the key details and fill your profile automatically.
              </p>
            </div>

            <ResumeDropZone
              resumeFile={resumeFile}
              isDragging={isDragging}
              uploading={uploading}
              onFile={handleFile}
              onDragOver={e => { e.preventDefault(); setIsDragging(true) }}
              onDragLeave={e => { e.preventDefault(); setIsDragging(false) }}
              onDrop={e => {
                e.preventDefault()
                setIsDragging(false)
                const f = e.dataTransfer.files?.[0]
                if (f) handleFile(f)
              }}
              fileInputRef={fileInputRef}
            />

            {uploadError && (
              <p className="text-[12px] text-[#81543c]">{uploadError}</p>
            )}

            <div className="flex items-center justify-between gap-3 mt-1">
              <button
                onClick={() => setPhase('choice')}
                className="text-[14px] text-[#645e57] hover:text-[#2f3333] transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={handleUpload}
                disabled={!resumeFile || uploading}
                className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
              >
                {uploading ? 'Reading...' : resumeFile ? 'Continue →' : 'Upload resume →'}
              </button>
            </div>
          </div>
        )}

        {/* ── Q1: Seniority ── */}
        {phase === 'q1' && (
          <div className="flex flex-col gap-5">
            <div>
              <p className="label-caps text-[11px] text-[#645e57] mb-3">QUESTION 1 OF 3</p>
              <h2 className="font-headline text-[1.5rem] text-[#2f3333] leading-tight">
                How senior are you in your field?
              </h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {SENIORITY_OPTIONS.map(opt => (
                <button
                  key={opt}
                  onClick={() => setQ1Answer(opt)}
                  className={`px-4 py-2 rounded-full text-[13px] transition-all duration-150 ${
                    q1Answer === opt
                      ? 'bg-[#58614f] text-white'
                      : 'bg-[#edeeed] text-[#2f3333] hover:bg-[#e6e9e8]'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            <div className="flex items-center justify-between gap-3 mt-2">
              <button
                onClick={() => setPhase('choice')}
                className="text-[14px] text-[#645e57] hover:text-[#2f3333] transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={() => setPhase('q2')}
                disabled={!q1Answer}
                className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {/* ── Q2: Domain ── */}
        {phase === 'q2' && (
          <div className="flex flex-col gap-5">
            <div>
              <p className="label-caps text-[11px] text-[#645e57] mb-3">QUESTION 2 OF 3</p>
              <h2 className="font-headline text-[1.5rem] text-[#2f3333] leading-tight">
                What&apos;s your primary domain?
              </h2>
            </div>
            <div className="flex flex-wrap gap-2">
              {DOMAIN_OPTIONS.map(opt => (
                <button
                  key={opt}
                  onClick={() => setQ2Answer(opt)}
                  className={`px-4 py-2 rounded-full text-[13px] transition-all duration-150 ${
                    q2Answer === opt
                      ? 'bg-[#58614f] text-white'
                      : 'bg-[#edeeed] text-[#2f3333] hover:bg-[#e6e9e8]'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
            <div className="flex items-center justify-between gap-3 mt-2">
              <button
                onClick={() => setPhase('q1')}
                className="text-[14px] text-[#645e57] hover:text-[#2f3333] transition-colors"
              >
                ← Back
              </button>
              <button
                onClick={() => setPhase('q3')}
                disabled={!q2Answer}
                className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
              >
                Next →
              </button>
            </div>
          </div>
        )}

        {/* ── Q3: Achievement ── */}
        {phase === 'q3' && (
          <div className="flex flex-col gap-5">
            <div>
              <p className="label-caps text-[11px] text-[#645e57] mb-3">QUESTION 3 OF 3</p>
              <h2 className="font-headline text-[1.5rem] text-[#2f3333] leading-tight">
                What&apos;s one thing you&apos;ve done you&apos;re proud of?
              </h2>
            </div>
            <input
              className="input-editorial w-full px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
              placeholder="e.g. shipped a feature used by 10K people, closed our first enterprise deal"
              value={q3Answer}
              onChange={e => setQ3Answer(e.target.value)}
              autoFocus
            />
            <div className="flex items-center justify-between gap-3 mt-2">
              <button
                onClick={() => setPhase('q2')}
                className="text-[14px] text-[#645e57] hover:text-[#2f3333] transition-colors"
              >
                ← Back
              </button>
              <div className="flex items-center gap-3">
                <button
                  onClick={handleFallbackDone}
                  disabled={savingFallback}
                  className="text-[12px] text-[#2f3333]/40 hover:text-[#2f3333]/60 transition-colors"
                >
                  Skip this one
                </button>
                <button
                  onClick={handleFallbackDone}
                  disabled={savingFallback}
                  className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                >
                  {savingFallback ? 'Saving...' : 'Done →'}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}

// ── Auth screen ───────────────────────────────────────────────────────────────
function AuthScreen({ prefillTopic }: { prefillTopic: string }) {
  const { signIn, isLoaded } = useSignIn()
  const [loading, setLoading] = useState(false)

  async function handleGoogle() {
    if (!signIn || !isLoaded) return
    setLoading(true)
    const redirectTarget = prefillTopic.trim()
      ? `/first-post?topic=${encodeURIComponent(prefillTopic.trim())}`
      : '/first-post'

    try {
      await signIn.authenticateWithRedirect({
        strategy: 'oauth_google',
        redirectUrl: '/sso-callback',
        redirectUrlComplete: redirectTarget,
      })
    } catch (err) {
      console.error('[first-post] Google OAuth error:', err)
      setLoading(false)
    }
  }

  const emailHref = prefillTopic.trim()
    ? `/sign-up?redirect_url=${encodeURIComponent(`/first-post?topic=${prefillTopic.trim()}`)}`
    : '/sign-up?redirect_url=/first-post'

  return (
    <div className="w-full max-w-[480px] bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-8 py-10">
      <h1 className="font-headline text-[2rem] text-[#2f3333] mb-2 leading-tight">
        Let&apos;s build your first post.
      </h1>
      <p className="text-[0.95rem] text-[#2f3333]/65 mb-8 leading-relaxed">
        Takes about 2 minutes. No setup required.
      </p>

      <button
        onClick={handleGoogle}
        disabled={loading}
        className="w-full btn-primary text-white py-3 rounded-xl text-[14px] font-medium mb-4 disabled:opacity-60 disabled:cursor-not-allowed transition-opacity flex items-center justify-center gap-2.5"
      >
        {loading ? (
          <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
        ) : (
          <>
            <GoogleIcon />
            Continue with Google
          </>
        )}
      </button>

      {/* Divider */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex-1 h-px bg-[#aeb3b2]/20" />
        <span className="text-[12px] text-[#aeb3b2]">or</span>
        <div className="flex-1 h-px bg-[#aeb3b2]/20" />
      </div>

      <a
        href={emailHref}
        className="w-full flex items-center justify-center py-3 rounded-xl text-[14px] text-[#2f3333] hover:bg-[#f3f4f3] transition-colors ghost-border"
      >
        Continue with email
      </a>

      <p className="text-[11px] text-[#2f3333]/40 text-center mt-5">
        By continuing you agree to our terms. No credit card required.
      </p>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function FirstPostPage() {
  const { isLoaded, isSignedIn, user } = useUser()
  const router = useRouter()
  const searchParams = useSearchParams()
  const api = useApi()

  const [screen, setScreen] = useState(0)
  const [flowState, setFlowState] = useState<'form' | 'generating' | 'error' | 'draft' | 'gate' | 'intercept'>('form')
  const [draftState, setDraftState] = useState<DraftState | null>(null)
  const [copied, setCopied] = useState(false)
  const [profileChecked, setProfileChecked] = useState(false)
  const [prefillTopic, setPrefillTopic] = useState('')
  const [prefillApplied, setPrefillApplied] = useState(false)

  // Resume upload (Step 6) state
  const [resumeFile, setResumeFile] = useState<File | null>(null)
  const [resumeIsDragging, setResumeIsDragging] = useState(false)
  const [resumeUploading, setResumeUploading] = useState(false)
  const [resumeError, setResumeError] = useState('')
  const [resumeUploaded, setResumeUploaded] = useState(false)
  const [resumeSkipped, setResumeSkipped] = useState(false)
  const [resumeExtractedFields, setResumeExtractedFields] = useState<ExtractedProfile>({})
  const [fallbackExtractedFields, setFallbackExtractedFields] = useState<ExtractedProfile>({})
  const resumeFileInputRef = useRef<HTMLInputElement>(null)

  // Pending CTA destination — set when user clicks a CTA while resumeSkipped
  const [pendingDestination, setPendingDestination] = useState<'feed' | 'create' | null>(null)
  const [profileSaveError, setProfileSaveError] = useState('')

  const [answers, setAnswers] = useState<Answers>({
    role: '',
    roleLabel: '',
    topic: '',
    format: 'linkedin post',
    experienceType: '',
    experienceDetail: '',
    opinion: '',
    opinionIsCustom: false,
    audience: '',
    voiceSample: '',
  })

  // Aux state for fields tracked separately from the answers object
  const [customRole, setCustomRole] = useState('')
  const [customOpinion, setCustomOpinion] = useState('')
  const [selectedPills, setSelectedPills] = useState<string[]>([])
  const [audienceCustom, setAudienceCustom] = useState('')
  const showTopicHeader = Boolean(answers.topic.trim()) && screen > 0

  const updateAnswers = (patch: Partial<Answers>) =>
    setAnswers(prev => ({ ...prev, ...patch }))

  useEffect(() => {
    if (prefillApplied) return
    const queryTopic = (searchParams.get('topic') || '').trim()
    const sessionTopic = (sessionStorage.getItem(WELCOME_TOPIC_PREFILL_KEY) || '').trim()
    const resolvedTopic = queryTopic || sessionTopic

    if (resolvedTopic) {
      updateAnswers({ topic: resolvedTopic })
      setPrefillTopic(resolvedTopic)
      if (queryTopic) {
        sessionStorage.setItem(WELCOME_TOPIC_PREFILL_KEY, queryTopic)
      }
    }

    setPrefillApplied(true)
  }, [prefillApplied, searchParams])

  useEffect(() => {
    if (!isLoaded || !isSignedIn) return
    if (!answers.topic.trim()) return
    sessionStorage.removeItem(WELCOME_TOPIC_PREFILL_KEY)
  }, [isLoaded, isSignedIn, answers.topic])

  // If the user is already signed in with a completed profile, skip this flow
  useEffect(() => {
    if (!isLoaded) return
    if (!isSignedIn) {
      setProfileChecked(true)
      return
    }
    api.getProfile()
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json()
          if (data.has_profile) {
            router.replace('/')
            return
          }
        }
        setProfileChecked(true)
      })
      .catch(() => setProfileChecked(true))
  }, [isLoaded, isSignedIn])

  // ── Derived values ──────────────────────────────────────────────────────────
  const roleKey = (answers.role || 'other') as RoleKey
  const opinionBucket = ROLE_TO_BUCKET[roleKey]
  const opinions = OPINION_STATEMENTS[opinionBucket]
  const experiencePlaceholder = EXPERIENCE_PLACEHOLDER[roleKey]

  const roleSpecificPills = ROLE_AUDIENCE_PILLS[roleKey] ?? []
  const allAudiencePills = [
    ...roleSpecificPills,
    ...CORE_AUDIENCE_PILLS.filter(p => !roleSpecificPills.includes(p)),
  ]

  // ── Can-advance logic per screen ────────────────────────────────────────────
  function canAdvance(): boolean {
    switch (screen) {
      case 0: return answers.topic.trim().length >= 10
      case 1: return !!answers.role
      case 2: return !!answers.experienceType
      case 3:
        if (answers.opinionIsCustom) return customOpinion.trim().length > 0
        return !!answers.opinion
      default: return false
    }
  }

  function canAdvanceScreen4(): boolean {
    return selectedPills.length > 0 || audienceCustom.trim().length > 0
  }

  // ── Navigation handlers ─────────────────────────────────────────────────────
  function handleNext() {
    if (screen === 3 && answers.opinionIsCustom) {
      updateAnswers({ opinion: customOpinion })
    }
    setScreen(s => s + 1)
  }

  // ── Step 6: Resume upload handler — returns extracted fields or null ────────
  async function handleResumeUpload(): Promise<ExtractedProfile | null> {
    if (!resumeFile) return null
    setResumeUploading(true)
    setResumeError('')
    try {
      const res = await api.extractResume(resumeFile)
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed.' }))
        throw new Error(err.detail ?? 'Upload failed.')
      }
      const extracted: ExtractedProfile = await res.json()
      setResumeExtractedFields(extracted)
      setResumeUploaded(true)
      return extracted
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Upload failed.'
      setResumeError(msg)
      return null
    } finally {
      setResumeUploading(false)
    }
  }

  // ── Build merged profile from all sources (priority order) ─────────────────
  function buildMergedProfile(
    finalAnswers: Answers,
    resume: ExtractedProfile,
    fallback: ExtractedProfile,
  ) {
    // Priority: onboarding answers > resume extraction > fallback questions
    return {
      // Identity: resume extraction wins for name; role label for role
      name: resume.name || fallback.name || '',
      role: finalAnswers.roleLabel || resume.role || '',
      bio: finalAnswers.experienceDetail || resume.bio || fallback.bio || '',
      location: resume.location || '',
      // Audience: onboarding wins
      target_audience: finalAnswers.audience,
      // Lists: concatenate and deduplicate (onboarding > resume > fallback)
      topics_of_expertise: mergeStringArrays(
        resume.topics_of_expertise,
        fallback.topics_of_expertise,
      ),
      voice_descriptors: mergeStringArrays(
        resume.voice_descriptors,
      ),
      opinions: mergeStringArrays(
        finalAnswers.opinion ? [finalAnswers.opinion] : [],
        resume.opinions,
      ),
      words_to_avoid: [],
      writing_rules: [],
      writing_samples: mergeStringArrays(
        finalAnswers.voiceSample ? [finalAnswers.voiceSample] : [],
        resume.writing_samples,
        fallback.writing_samples,
      ),
      linkedin_style_notes: '',
      medium_style_notes: '',
      thread_style_notes: '',
    }
  }

  // ── Generate ────────────────────────────────────────────────────────────────
  // resumeFieldsOverride: pass extracted fields directly to avoid stale closure
  async function handleGenerate(resumeFieldsOverride?: ExtractedProfile) {
    const combined = [...selectedPills, audienceCustom.trim()]
      .filter(Boolean)
      .join(', ')
    const finalAnswers = { ...answers, audience: combined }
    updateAnswers({ audience: combined })
    setFlowState('generating')

    const effectiveResumeFields = resumeFieldsOverride ?? resumeExtractedFields
    const rawProfile = buildMergedProfile(finalAnswers, effectiveResumeFields, fallbackExtractedFields)
    const clerkName = [user?.firstName, user?.lastName].filter(Boolean).join(' ').trim()
    const emailPrefix = user?.primaryEmailAddress?.emailAddress?.split('@')[0] ?? ''
    const fallbackName = effectiveResumeFields?.name || clerkName || emailPrefix
    const profile = { ...rawProfile, name: rawProfile.name || fallbackName }

    setProfileSaveError('')
    console.log('[first-post] Saving profile with name:', profile.name)
    try {
      await api.saveProfile(profile)
      console.log('[first-post] Profile saved successfully for user')
    } catch (err) {
      console.error('[first-post] profile save error:', err)
      setFlowState('form')
      setProfileSaveError('Profile save failed — please try again.')
      return
    }

    let generatedPost = ''
    let score = 0
    let archetype = ''

    try {
      const res = await api.generatePost({
        topic: finalAnswers.topic,
        format: finalAnswers.format,
        tone: 'casual',
        context: buildContext(finalAnswers),
      })

      if (!res.ok) {
        throw new Error(`POST /generate failed with status ${res.status}`)
      }

      const data = await res.json()
      generatedPost = data.post || ''
      score = data.score || 0
      archetype = data.archetype || ''

      if (!generatedPost) {
        throw new Error('Generated post was empty')
      }
    } catch (err) {
      console.error('[first-post] generate error:', err)
      setFlowState('error')
      return
    }

    let postId: number | null = null
    try {
      const logRes = await api.logPost({
        topic: finalAnswers.topic,
        format: finalAnswers.format,
        tone: 'casual',
        content: generatedPost,
        authenticity_score: score || 0,
        svg_diagrams: null,
        archetype: archetype || '',
      })

      if (logRes.ok) {
        const logData = await logRes.json()
        postId = typeof logData?.post_id === 'number' ? logData.post_id : null
      }
    } catch (err) {
      console.error('[first-post] log post error:', err)
    }

    setDraftState({ post: generatedPost, score, archetype, postId })
    setFlowState('draft')
  }

  function persistDraftToSession() {
    if (!draftState) return

    sessionStorage.setItem('contentOS_last_post', draftState.post)
    sessionStorage.setItem('contentOS_last_topic', answers.topic)
    sessionStorage.setItem('contentOS_last_format', answers.format)
    sessionStorage.setItem('contentOS_last_tone', 'casual')
    sessionStorage.setItem('contentOS_last_score', String(draftState.score || 0))
    sessionStorage.setItem('contentOS_last_feedback', JSON.stringify([]))
    sessionStorage.setItem('contentOS_last_iterations', '1')
    sessionStorage.setItem('contentOS_last_scored', String((draftState.score || 0) > 0))
    sessionStorage.setItem('contentOS_last_topic_meta', answers.topic)
    sessionStorage.setItem('contentOS_last_format_meta', answers.format)
    sessionStorage.setItem('contentOS_last_tone_meta', 'casual')

    if (draftState.postId) {
      sessionStorage.setItem('contentOS_current_post_id', String(draftState.postId))
    }
  }

  function handleCopyPost() {
    if (!draftState?.post) return

    navigator.clipboard.writeText(draftState.post).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    }).catch((err) => {
      console.error('[first-post] copy error:', err)
    })
  }

  // ── CTA interception ─────────────────────────────────────────────────────────
  function handleCTA(destination: 'feed' | 'create') {
    if (resumeSkipped) {
      setPendingDestination(destination)
      setFlowState('gate')
    } else {
      persistDraftToSession()
      const interceptDone = typeof window !== 'undefined' && localStorage.getItem('contendo_intercept_done') === '1'
      if (!interceptDone) {
        setPendingDestination(destination)
        setFlowState('intercept')
      } else {
        router.push(destination === 'feed' ? '/' : '/create')
      }
    }
  }

  // Called by ProfileGate when extraction is done — pass fields directly to avoid stale closure
  async function handleGateExtracted(fields: ExtractedProfile) {
    setFallbackExtractedFields(fields)
    const combined = [...selectedPills, audienceCustom.trim()].filter(Boolean).join(', ')
    const finalAnswers = { ...answers, audience: combined }
    // For gate, the resume slot is already set; fallback fills in the rest
    const rawProfile = buildMergedProfile(finalAnswers, resumeExtractedFields, fields)
    const clerkName = [user?.firstName, user?.lastName].filter(Boolean).join(' ').trim()
    const emailPrefix = user?.primaryEmailAddress?.emailAddress?.split('@')[0] ?? ''
    const fallbackName = fields?.name || resumeExtractedFields?.name || clerkName || emailPrefix
    const profile = { ...rawProfile, name: rawProfile.name || fallbackName }
    try {
      await api.saveProfile(profile)
      console.log('[first-post] Gate profile saved successfully for user')
    } catch (err) {
      console.error('[first-post] gate profile save error:', err)
    }
  }

  function handleGateDone() {
    persistDraftToSession()
    router.push(pendingDestination === 'feed' ? '/' : '/create')
  }

  function handleGateSkip() {
    persistDraftToSession()
    router.push(pendingDestination === 'feed' ? '/' : '/create')
  }

  // ── Render guards ───────────────────────────────────────────────────────────
  if (!isLoaded || (isSignedIn && !profileChecked)) {
    return (
      <div className="min-h-screen bg-[#faf9f8] flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-[#58614f]/30 border-t-[#58614f] rounded-full animate-spin" />
      </div>
    )
  }

  if (flowState === 'generating') {
    return <GeneratingScreen />
  }

  if (flowState === 'error') {
    return <GenerateErrorScreen onGoToWorkspace={() => router.push('/create')} />
  }

  if (flowState === 'gate') {
    return (
      <ProfileGate
        api={api}
        onExtracted={handleGateExtracted}
        onDone={handleGateDone}
        onSkip={handleGateSkip}
      />
    )
  }

  if (flowState === 'intercept') {
    const dest = pendingDestination === 'feed' ? '/' : '/create'
    return (
      <OnboardingIntercept
        destination={dest}
      />
    )
  }

  if (flowState === 'draft' && draftState) {
    return (
      <DraftScreen
        topic={answers.topic}
        format={answers.format}
        post={draftState.post}
        score={draftState.score}
        copied={copied}
        onCopy={handleCopyPost}
        onFeedMemory={() => handleCTA('feed')}
        onCreate={() => handleCTA('create')}
      />
    )
  }

  // ── Main layout ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      <Wordmark />

      {!isSignedIn ? (
        <>
          {showTopicHeader && (
            <p className="text-[11px] text-[#2f3333]/50 label-caps tracking-[0.06em] text-center mb-3">
              Writing about: {answers.topic.trim()}
            </p>
          )}
          <AuthScreen prefillTopic={prefillTopic || answers.topic} />
        </>
      ) : (
        <div className="w-full max-w-[600px]">
          {showTopicHeader && (
            <p className="text-[11px] text-[#2f3333]/50 label-caps tracking-[0.06em] text-center mb-3">
              Writing about: {answers.topic.trim()}
            </p>
          )}
          <div className="bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-8 py-10">
            <StepDots total={6} current={screen} />

            {/* Screen content — key triggers step-animate on transition */}
            <div key={screen} className="step-animate flex flex-col gap-5">

              {/* ── Screen 0: Topic + Format ────────────────────────────────── */}
              {screen === 0 && (
                <>
                  <div>
                    <h2 className="font-headline text-[1.75rem] text-[#2f3333] mb-2 leading-tight">
                      What do you want to write about?
                    </h2>
                    <p className="text-[0.9rem] text-[#645e57]">
                      Be specific — the more focused the topic, the stronger the post.
                    </p>
                  </div>

                  <div className="flex flex-col gap-1.5">
                    <label className="label-caps text-[#645e57] text-[11px]">
                      Your Topic
                    </label>
                    <input
                      className="input-editorial w-full px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
                      placeholder="e.g. Why most ML models fail before they reach production"
                      value={answers.topic}
                      onChange={e => updateAnswers({ topic: e.target.value })}
                      autoFocus
                    />
                  </div>

                  <div className="flex flex-col gap-2">
                    <label className="label-caps text-[#645e57] text-[11px]">
                      Format
                    </label>
                    <div className="flex gap-2">
                      {[
                        { key: 'linkedin post',  label: 'LinkedIn Post' },
                        { key: 'medium article', label: 'Medium Article' },
                      ].map(f => (
                        <button
                          key={f.key}
                          onClick={() => updateAnswers({ format: f.key })}
                          className={`px-4 py-2 rounded-full text-[13px] transition-all duration-150 ${
                            answers.format === f.key
                              ? 'bg-[#58614f] text-white'
                              : 'bg-[#edeeed] text-[#2f3333] hover:bg-[#e6e9e8]'
                          }`}
                        >
                          {f.label}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              )}

              {/* ── Screen 1: Role picker ───────────────────────────────────── */}
              {screen === 1 && (
                <>
                  <div>
                    <h2 className="font-headline text-[1.75rem] text-[#2f3333] mb-2 leading-tight">
                      What best describes your work?
                    </h2>
                    <p className="text-[0.9rem] text-[#645e57]">
                      This shapes which insights we surface for you.
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-2.5">
                    {ROLE_OPTIONS.map(role => (
                      <button
                        key={role.key}
                        onClick={() =>
                          updateAnswers({ role: role.key, roleLabel: role.label })
                        }
                        className={`flex flex-col items-center justify-center gap-2 h-[90px] rounded-xl px-2 transition-all duration-150 ${
                          answers.role === role.key
                            ? 'bg-[#edeeed] border-l-[3px] border-l-[#58614f]'
                            : 'bg-[#f3f4f3] hover:bg-[#edeeed]'
                        }`}
                      >
                        <span
                          className={
                            answers.role === role.key
                              ? 'text-[#58614f]'
                              : 'text-[#645e57]'
                          }
                        >
                          {ROLE_ICONS[role.key]}
                        </span>
                        <span
                          className={`text-[12px] text-center leading-tight ${
                            answers.role === role.key
                              ? 'text-[#58614f] font-medium'
                              : 'text-[#2f3333]'
                          }`}
                        >
                          {role.label}
                        </span>
                      </button>
                    ))}
                  </div>

                  {/* Slide-in custom role input when 'other' is selected */}
                  <div
                    style={{
                      maxHeight: answers.role === 'other' ? '100px' : '0',
                      overflow: 'hidden',
                      transition: 'max-height 200ms ease',
                    }}
                  >
                    <div className="flex flex-col gap-1.5 pt-1">
                      <label className="label-caps text-[#645e57] text-[11px]">
                        What do you do?
                      </label>
                      <input
                        className="input-editorial w-full px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
                        placeholder="Describe your role..."
                        value={customRole}
                        onChange={e => {
                          setCustomRole(e.target.value)
                          updateAnswers({
                            roleLabel: e.target.value || 'Something else',
                          })
                        }}
                      />
                    </div>
                  </div>
                </>
              )}

              {/* ── Screen 2: Experience type ───────────────────────────────── */}
              {screen === 2 && (
                <>
                  <div>
                    <h2 className="font-headline text-[1.75rem] text-[#2f3333] mb-2 leading-tight">
                      What should your post draw from?
                    </h2>
                    <p className="text-[0.9rem] text-[#645e57]">
                      Pick the type of experience that fits best.
                    </p>
                  </div>

                  <div className="flex flex-col gap-2">
                    {EXPERIENCE_OPTIONS.map(opt => (
                      <div key={opt.key}>
                        <button
                          onClick={() =>
                            updateAnswers({ experienceType: opt.key })
                          }
                          className={`w-full flex items-center gap-3 px-4 py-4 rounded-xl transition-all duration-150 text-left ${
                            answers.experienceType === opt.key
                              ? 'bg-[#edeeed] border-l-[3px] border-l-[#58614f]'
                              : 'bg-[#f3f4f3] hover:bg-[#edeeed]'
                          }`}
                        >
                          <div
                            className={`w-2 h-2 rounded-full flex-shrink-0 transition-colors ${
                              answers.experienceType === opt.key
                                ? 'bg-[#58614f]'
                                : 'bg-[#aeb3b2]/40'
                            }`}
                          />
                          <div>
                            <p className="text-[14px] font-medium text-[#2f3333] leading-snug">
                              {opt.label}
                            </p>
                            <p className="text-[12px] text-[#2f3333]/55 mt-0.5">
                              {opt.sublabel}
                            </p>
                          </div>
                        </button>

                        {/* Slide-in one-sentence detail input */}
                        <div
                          style={{
                            maxHeight:
                              answers.experienceType === opt.key ? '120px' : '0',
                            overflow: 'hidden',
                            transition: 'max-height 200ms ease',
                          }}
                        >
                          <div className="pt-2 pl-8">
                            <label className="label-caps text-[#645e57] text-[11px]">
                              Give me one sentence about it
                            </label>
                            <input
                              className="input-editorial w-full px-3 py-2.5 mt-1 text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
                              placeholder={experiencePlaceholder}
                              value={answers.experienceDetail}
                              onChange={e =>
                                updateAnswers({ experienceDetail: e.target.value })
                              }
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )}

              {/* ── Screen 3: Opinion picker ────────────────────────────────── */}
              {screen === 3 && (
                <>
                  <div>
                    <h2 className="font-headline text-[1.75rem] text-[#2f3333] mb-2 leading-tight">
                      Pick the take closest to yours.
                    </h2>
                    <p className="text-[0.9rem] text-[#645e57]">
                      This becomes the spine of your post.
                    </p>
                  </div>

                  <div className="flex flex-col gap-2">
                    {opinions.map((statement, i) => {
                      const isSelected =
                        answers.opinion === statement && !answers.opinionIsCustom
                      return (
                        <button
                          key={i}
                          onClick={() =>
                            updateAnswers({
                              opinion: statement,
                              opinionIsCustom: false,
                            })
                          }
                          className={`w-full flex items-start gap-3 px-4 py-4 rounded-xl transition-all duration-150 text-left ${
                            isSelected
                              ? 'bg-[#edeeed] border-l-[3px] border-l-[#58614f]'
                              : 'bg-[#f3f4f3] hover:bg-[#edeeed]'
                          }`}
                        >
                          <span className="text-[#58614f] text-[1.5rem] leading-none mt-[-2px] font-serif flex-shrink-0">
                            &ldquo;
                          </span>
                          <span className="text-[14px] text-[#2f3333] leading-relaxed flex-1">
                            {statement}
                          </span>
                          {isSelected && (
                            <span className="flex-shrink-0 text-[#58614f] mt-0.5">
                              <CheckIcon />
                            </span>
                          )}
                        </button>
                      )
                    })}

                    {/* Escape hatch */}
                    <div>
                      <button
                        onClick={() =>
                          updateAnswers({ opinion: '', opinionIsCustom: true })
                        }
                        className={`w-full px-4 py-4 rounded-xl transition-all duration-150 text-left text-[14px] ${
                          answers.opinionIsCustom
                            ? 'bg-[#edeeed] border-l-[3px] border-l-[#58614f] text-[#2f3333]'
                            : 'text-[#645e57] hover:bg-[#f3f4f3]'
                        }`}
                        style={
                          !answers.opinionIsCustom
                            ? { border: '1px dashed rgba(174, 179, 178, 0.2)' }
                            : undefined
                        }
                      >
                        None of these — I&apos;ll write my own
                      </button>

                      {/* Slide-in custom textarea */}
                      <div
                        style={{
                          maxHeight: answers.opinionIsCustom ? '150px' : '0',
                          overflow: 'hidden',
                          transition: 'max-height 200ms ease',
                        }}
                      >
                        <textarea
                          className="input-editorial w-full px-3 py-2.5 mt-2 text-[14px] text-[#2f3333] placeholder-[#aeb3b2] resize-none"
                          rows={3}
                          placeholder="Write your take in one sentence..."
                          value={customOpinion}
                          onChange={e => setCustomOpinion(e.target.value)}
                          autoFocus={answers.opinionIsCustom}
                        />
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* ── Screen 4: Audience + Voice sample ──────────────────────── */}
              {screen === 4 && (
                <>
                  <div>
                    <h2 className="font-headline text-[1.75rem] text-[#2f3333] mb-2 leading-tight">
                      Who are you writing for?
                    </h2>
                    <p className="text-[0.9rem] text-[#645e57]">
                      And how do you actually sound?
                    </p>
                  </div>

                  {/* Audience section */}
                  <div className="flex flex-col gap-2">
                    <label className="label-caps text-[#645e57] text-[11px]">
                      Your Audience
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {allAudiencePills.map(pill => (
                        <button
                          key={pill}
                          onClick={() =>
                            setSelectedPills(prev =>
                              prev.includes(pill)
                                ? prev.filter(p => p !== pill)
                                : [...prev, pill]
                            )
                          }
                          className={`px-3 py-1.5 rounded-full text-[12px] label-caps transition-all duration-150 ${
                            selectedPills.includes(pill)
                              ? 'bg-[#58614f] text-white'
                              : 'bg-[#edeeed] text-[#2f3333] hover:bg-[#e6e9e8]'
                          }`}
                        >
                          {pill}
                        </button>
                      ))}
                    </div>
                    <input
                      className="input-editorial w-full px-3 py-2.5 mt-1 text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
                      placeholder="Or describe your audience..."
                      value={audienceCustom}
                      onChange={e => setAudienceCustom(e.target.value)}
                    />
                  </div>

                  <div className="h-1" />

                  {/* Voice sample section */}
                  <div className="flex flex-col gap-2">
                    <div>
                      <label className="label-caps text-[#645e57] text-[11px]">
                        How you sound (optional but powerful)
                      </label>
                      <p className="text-[12px] text-[#2f3333]/55 mt-1 leading-relaxed">
                        Paste anything you&apos;ve written — a tweet, Slack message,
                        email, even one sentence. This is the strongest signal we have
                        for matching your voice.
                      </p>
                    </div>
                    <textarea
                      className="input-editorial w-full px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2] resize-none"
                      rows={4}
                      placeholder={`e.g. 'Shipped the feature. Broke prod. Fixed it. Shipped again. Worth it.' — anything real works.`}
                      value={answers.voiceSample}
                      onChange={e => updateAnswers({ voiceSample: e.target.value })}
                    />
                  </div>

                  <p className="text-[12px] text-[#2f3333]/40 text-center">
                    You can always update these later.
                  </p>
                </>
              )}

              {/* ── Screen 5: Resume upload ─────────────────────────────────── */}
              {screen === 5 && (
                <>
                  <div>
                    <h2 className="font-headline italic text-[1.75rem] text-[#2f3333] mb-2 leading-tight">
                      One last thing
                    </h2>
                    <p className="text-[0.9rem] text-[#645e57] leading-relaxed">
                      Upload your resume and we&apos;ll fill your profile automatically —
                      so your first post actually sounds like you.
                    </p>
                  </div>

                  <ResumeDropZone
                    resumeFile={resumeFile}
                    isDragging={resumeIsDragging}
                    uploading={resumeUploading}
                    onFile={f => { setResumeFile(f); setResumeError('') }}
                    onDragOver={e => { e.preventDefault(); setResumeIsDragging(true) }}
                    onDragLeave={e => { e.preventDefault(); setResumeIsDragging(false) }}
                    onDrop={e => {
                      e.preventDefault()
                      setResumeIsDragging(false)
                      const f = e.dataTransfer.files?.[0]
                      if (f) { setResumeFile(f); setResumeError('') }
                    }}
                    fileInputRef={resumeFileInputRef}
                  />

                  {resumeError && (
                    <p className="text-[12px] text-[#81543c]">{resumeError}</p>
                  )}
                </>
              )}

            </div>

            {/* ── Navigation ─────────────────────────────────────────────────── */}
            <div
              className={`flex items-center gap-3 mt-8 ${
                screen === 0 ? 'justify-end' : 'justify-between'
              }`}
            >
              {screen > 0 && (
                <button
                  onClick={() => setScreen(s => s - 1)}
                  className="text-[14px] text-[#645e57] hover:text-[#2f3333] transition-colors"
                >
                  ← Back
                </button>
              )}

              {screen < 4 ? (
                <button
                  onClick={handleNext}
                  disabled={!canAdvance()}
                  className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                >
                  Next
                </button>
              ) : screen === 4 ? (
                <button
                  onClick={handleNext}
                  disabled={!canAdvanceScreen4()}
                  className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                >
                  Next
                </button>
              ) : (
                /* Screen 5 — resume upload + generate */
                <div className="flex flex-col items-end gap-3 w-full">
                  {profileSaveError && (
                    <p className="text-[12px] text-red-500 w-full text-right">{profileSaveError}</p>
                  )}
                  <button
                    onClick={async () => {
                      if (resumeFile) {
                        // Extract fields directly, pass to generate to avoid stale state closure
                        const fields = await handleResumeUpload()
                        if (fields !== null) {
                          await handleGenerate(fields)
                        }
                        // if fields is null, extraction failed — stay on screen with error
                      } else {
                        await handleGenerate()
                      }
                    }}
                    disabled={resumeUploading}
                    className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                  >
                    {resumeUploading
                      ? 'Reading your resume...'
                      : resumeFile
                        ? 'Upload resume →'
                        : 'Generate my first post →'}
                  </button>
                  <button
                    onClick={() => {
                      setResumeSkipped(true)
                      handleGenerate()
                    }}
                    className="text-[12px] text-[#2f3333]/40 hover:text-[#2f3333]/60 transition-colors"
                  >
                    Skip for now
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
