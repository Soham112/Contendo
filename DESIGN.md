# Design System Specification: The Editorial Workspace

## 1. Overview & Creative North Star
**Creative North Star: The Digital Atelier**

This design system is built to transform a content generation platform into a serene, high-end creative sanctuary. We are moving away from the "SaaS dashboard" aesthetic—which is often cold, grid-locked, and utilitarian—and moving toward an **Editorial Atelier** experience. 

The system prioritizes the "Writer’s Flow." It breaks the traditional template look through **intentional asymmetry**, where text-heavy columns are balanced by generous, breathing whitespace. We treat the screen not as a UI to be managed, but as a digital canvas to be composed. By utilizing high-contrast typography scales and overlapping tonal layers, we create a sense of focused sophistication that feels personal, quiet, and deeply intentional.

---

## 2. Colors & Surface Architecture
The palette is rooted in warmth, moving away from sterile pure whites and toward a tactile, paper-like experience.

### The Palette (Material Design Mapping)
*   **Primary (Sage):** `#58614f` – Used for moments of focus and quiet action.
*   **Secondary (Warm Gray):** `#645e57` – For functional elements that sit back.
*   **Tertiary (Terracotta):** `#81543c` – For highlights, calls to inspiration, or delicate alerts.
*   **Background:** `#faf9f8` – A soft, off-white "paper" base.
*   **On-Surface (Charcoal):** `#2f3333` – Deep, high-contrast text for ultimate legibility.

### The "No-Line" Rule
To maintain the editorial feel, **1px solid borders are strictly prohibited for sectioning.** We do not "box in" creativity. Instead:
*   **Tonal Transitions:** Use `surface-container-low` (`#f3f4f3`) against the `background` to define sidebars or headers.
*   **Whitespace as Divider:** Use the Spacing Scale (specifically `8` to `12` units) to create "invisible" boundaries.

### Surface Hierarchy & Nesting
Treat the UI as a series of stacked, fine-milled paper sheets. 
*   **Level 0:** `background` (#faf9f8) with a 2% noise/grain texture overlay.
*   **Level 1:** `surface-container` (#edeeed) for main content areas.
*   **Level 2:** `surface-container-highest` (#dfe3e2) for floating contextual menus.

### The "Glass & Gradient" Rule
For floating elements like toolbars or "AI Sparkle" menus, use **Glassmorphism**. Apply a semi-transparent version of `surface-container-lowest` with a `20px` backdrop-blur. To give buttons "soul," use a subtle linear gradient from `primary` (#58614f) to `primary-dim` (#4c5543) at a 135-degree angle.

---

## 3. Typography
The typography is the voice of the system. It balances the authority of a literary journal with the clarity of a modern workspace.

*   **Display & Headlines (Noto Serif):** These are your "Editorial Anchors." Use `display-lg` (3.5rem) for hero titles. The serif nature conveys wisdom and craftsmanship.
*   **Body (Inter):** The "Workhorse." Inter provides a neutral, high-legibility counterpoint to the Serif headings. 
    *   **Body-lg (1rem):** Used for the primary writing experience with a generous `1.6` line-height.
*   **Labels & Metadata:** Use `label-md` (0.75rem) in all-caps with `0.05rem` letter spacing to differentiate functional data from creative content.

---

## 4. Elevation & Depth
We reject harsh, "drop-shadow-default" styles. Depth is organic and atmospheric.

*   **Tonal Layering:** Place a `surface-container-lowest` (#ffffff) card on top of a `surface-container` background to create a "lifted" effect without any shadow at all.
*   **Ambient Shadows:** If an element must float (like a modal), use a triple-layered shadow:
    *   `0px 4px 20px rgba(47, 51, 51, 0.04)`
    *   `0px 12px 40px rgba(47, 51, 51, 0.06)`
    *   Shadow color should always be a tint of `on-surface`, never pure black.
*   **The Ghost Border:** If accessibility requires a border, use `outline-variant` (#aeb3b2) at **15% opacity**. It should be felt, not seen.

---

## 5. Components

### Buttons
*   **Primary:** Rounded `md` (0.75rem). Gradient fill (Primary to Primary-Dim). White text.
*   **Secondary:** Ghost style. No background, `on-surface` text, and a `Ghost Border` that only appears on hover.
*   **Tertiary:** Text-only with a subtle `tertiary-fixed-dim` underline that grows on hover.

### Input Fields
*   **Design:** Forgo the "4-sided box." Use a `surface-container-low` background with a slightly thicker bottom-border in `primary` when focused.
*   **Typography:** User input should always use `body-lg` to prioritize the content being created.

### Cards & Lists
*   **No Dividers:** Lists should be separated by `spacing-4` (1.4rem). 
*   **Card Styling:** Use `rounded-lg` (1rem). Instead of a border, use a subtle shift to `surface-container-highest` on hover to indicate interactivity.

### Contextual Writing Toolbar
*   **Style:** A floating glassmorphic pill (`rounded-full`) using `surface-container-lowest` at 80% opacity. This "hovers" over the text, keeping the focus on the words.

---

## 6. Do’s and Don’ts

### Do
*   **DO** use asymmetrical margins. A wider left margin for text can create a sophisticated "book" feel.
*   **DO** embrace the grain. A 1-2% monochromatic noise filter on the background prevents the "digital fatigue" of flat colors.
*   **DO** use `tertiary` (Terracotta) sparingly—only for high-value inspiration or critical actions.

### Don’t
*   **DON'T** use 100% opaque black for text. Always use `on-surface` (#2f3333) to keep the contrast "warm."
*   **DON'T** use sharp corners. Everything in this workspace should feel soft to the touch; adhere strictly to the `8-12px` (md to lg) roundedness scale.
*   **DON'T** crowd the screen. If a feature isn't essential to the current task, hide it in a secondary surface layer.