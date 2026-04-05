'use client'

import { useState } from 'react'
import { useUser, useSignIn } from '@clerk/nextjs'
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

// ── Auth screen ───────────────────────────────────────────────────────────────
function AuthScreen() {
  const { signIn, isLoaded } = useSignIn()
  const [loading, setLoading] = useState(false)

  async function handleGoogle() {
    if (!signIn || !isLoaded) return
    setLoading(true)
    try {
      await signIn.authenticateWithRedirect({
        strategy: 'oauth_google',
        redirectUrl: '/sso-callback',
        redirectUrlComplete: '/first-post',
      })
    } catch (err) {
      console.error('[first-post] Google OAuth error:', err)
      setLoading(false)
    }
  }

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
        href="/sign-up?redirect_url=/first-post"
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
  const { isLoaded, isSignedIn } = useUser()

  const [screen, setScreen] = useState(0)
  const [isGenerating, setIsGenerating] = useState(false)

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

  const updateAnswers = (patch: Partial<Answers>) =>
    setAnswers(prev => ({ ...prev, ...patch }))

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
      case 0: return !!answers.role
      case 1: return answers.topic.trim().length >= 10
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
    // Flush custom opinion into answers before leaving screen 3
    if (screen === 3 && answers.opinionIsCustom) {
      updateAnswers({ opinion: customOpinion })
    }
    setScreen(s => s + 1)
  }

  function handleGenerate() {
    const combined = [...selectedPills, audienceCustom.trim()]
      .filter(Boolean)
      .join(', ')
    const finalAnswers = { ...answers, audience: combined }
    console.log('[first-post] answers:', finalAnswers)
    updateAnswers({ audience: combined })
    setIsGenerating(true)
  }

  // ── Render guards ───────────────────────────────────────────────────────────
  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-[#faf9f8] flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-[#58614f]/30 border-t-[#58614f] rounded-full animate-spin" />
      </div>
    )
  }

  if (isGenerating) {
    return <GeneratingScreen />
  }

  // ── Main layout ─────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      <Wordmark />

      {!isSignedIn ? (
        <AuthScreen />
      ) : (
        <div className="w-full max-w-[600px]">
          <div className="bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-8 py-10">
            <StepDots total={5} current={screen} />

            {/* Screen content — key triggers step-animate on transition */}
            <div key={screen} className="step-animate flex flex-col gap-5">

              {/* ── Screen 0: Role picker ───────────────────────────────────── */}
              {screen === 0 && (
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

              {/* ── Screen 1: Topic + Format ────────────────────────────────── */}
              {screen === 1 && (
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
                        { key: 'thread',         label: 'Thread' },
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
              ) : (
                <button
                  onClick={handleGenerate}
                  disabled={!canAdvanceScreen4()}
                  className="btn-primary text-white px-6 py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
                >
                  Generate my first post →
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
