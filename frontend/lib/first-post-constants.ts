// All hardcoded data for the /first-post flow

export type RoleKey =
  | 'data_ml'
  | 'data_eng'
  | 'product'
  | 'software'
  | 'design'
  | 'founder'
  | 'marketer'
  | 'consultant'
  | 'other'

export interface RoleOption {
  key: RoleKey
  label: string
}

export const ROLE_OPTIONS: RoleOption[] = [
  { key: 'data_ml',    label: 'Data Scientist / ML Engineer' },
  { key: 'data_eng',   label: 'Data Engineer / Analytics Engineer' },
  { key: 'product',    label: 'Product Manager' },
  { key: 'software',   label: 'Software Engineer' },
  { key: 'design',     label: 'Designer (UX/Product)' },
  { key: 'founder',    label: 'Founder / Operator' },
  { key: 'marketer',   label: 'Marketer / Growth' },
  { key: 'consultant', label: 'Consultant / Advisor' },
  { key: 'other',      label: 'Something else' },
]

// ── Role → opinion bucket mapping ────────────────────────────────────────────
export type OpinionBucket = 'data' | 'product' | 'engineering' | 'founder'

export const ROLE_TO_BUCKET: Record<RoleKey, OpinionBucket> = {
  data_ml:    'data',
  data_eng:   'data',
  product:    'product',
  design:     'product',
  software:   'engineering',
  founder:    'founder',
  marketer:   'founder',
  consultant: 'founder',
  other:      'founder',
}

// ── Opinion statements per bucket ────────────────────────────────────────────
export const OPINION_STATEMENTS: Record<OpinionBucket, string[]> = {
  data: [
    'Most ML models fail in production because of data quality, not model quality',
    'Feature engineering is still more valuable than model architecture in 2025',
    'The gap between a Jupyter notebook and a production system is where most projects die',
    "Stakeholders asking for AI when they need a spreadsheet is the industry's biggest waste",
    'Real-time ML is overhyped for 80% of use cases',
  ],
  product: [
    'Most roadmaps are just lists of features nobody asked for',
    "The best product decisions I've made came from watching users, not analyzing metrics",
    'Design systems save teams from themselves',
    "PMs who can't say no are just project managers with better titles",
    'User research is the most underfunded part of any product team',
  ],
  engineering: [
    'The best engineers I know write less code, not more',
    'Most technical debt is just undocumented decisions',
    'Code reviews are more about culture than catching bugs',
    'Microservices were the wrong answer for most teams that adopted them',
    "The tools don't matter as much as the team's ability to use them well",
  ],
  founder: [
    'Most startups die from lack of focus, not lack of ideas',
    "The best marketing is just being specific about who you're NOT for",
    'Hiring for culture fit is just bias with better branding',
    "Most 'data-driven' decisions are actually gut calls in disguise",
    "Speed beats perfection until it suddenly doesn't",
  ],
}

// ── Experience type options ───────────────────────────────────────────────────
export interface ExperienceOption {
  key: string
  label: string
  sublabel: string
}

export const EXPERIENCE_OPTIONS: ExperienceOption[] = [
  {
    key: 'failure',
    label: 'A specific failure or mistake',
    sublabel: 'What went wrong and what you learned',
  },
  {
    key: 'project',
    label: 'Something I learned from a recent project',
    sublabel: 'A lesson from hands-on work',
  },
  {
    key: 'observation',
    label: 'An observation about my industry',
    sublabel: 'A pattern you keep noticing',
  },
  {
    key: 'decision',
    label: 'A decision that turned out differently than expected',
    sublabel: 'The gap between what you planned and what happened',
  },
  {
    key: 'pattern',
    label: 'A pattern I keep seeing across my work',
    sublabel: 'Something you notice repeatedly',
  },
]

// ── Experience detail placeholder per role ────────────────────────────────────
export const EXPERIENCE_PLACEHOLDER: Record<RoleKey, string> = {
  data_ml:    'e.g. We spent 3 months on a model that got replaced by a SQL query',
  data_eng:   'e.g. Our pipeline looked clean until we traced a bug to day 1 of ingestion',
  product:    'e.g. We shipped a feature nobody asked for and it became our most used one',
  software:   "e.g. I rewrote a service in a 'better' language and it was slower",
  design:     'e.g. Users ignored the button I spent 2 weeks designing',
  founder:    'e.g. We pivoted away from our best feature because one customer complained',
  marketer:   'e.g. Our worst-written email had our highest open rate ever',
  consultant: 'e.g. The client ignored my recommendation then hired me to fix the result',
  other:      'e.g. Something that surprised you about how things actually work',
}

// ── Audience pills ────────────────────────────────────────────────────────────
export const CORE_AUDIENCE_PILLS: string[] = [
  'startup founders',
  'senior engineers',
  'product managers',
  'data scientists',
  'non-technical executives',
  'early-career professionals',
]

export const ROLE_AUDIENCE_PILLS: Partial<Record<RoleKey, string[]>> = {
  data_ml:    ['ML engineers', 'data teams', 'analytics leaders'],
  data_eng:   ['ML engineers', 'data teams', 'analytics leaders'],
  product:    ['product designers', 'UX researchers', 'CPOs'],
  design:     ['product designers', 'UX researchers', 'CPOs'],
  software:   ['backend engineers', 'engineering managers', 'CTOs'],
  founder:    ['B2B founders', 'growth teams', 'investors'],
  marketer:   ['B2B founders', 'growth teams', 'investors'],
  consultant: ['consulting clients', 'procurement teams', 'C-suite'],
}
