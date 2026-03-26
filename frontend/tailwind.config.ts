import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        headline: ["Noto Serif", "Georgia", "serif"],
        body: ["Inter", "system-ui", "sans-serif"],
        label: ["Inter", "system-ui", "sans-serif"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      colors: {
        // Core palette — DESIGN.md tokens
        "primary":                    "#58614f",
        "primary-dim":                "#4c5543",
        "primary-fixed":              "#dce6ce",
        "primary-fixed-dim":          "#ced8c1",
        "primary-container":          "#dce6ce",
        "on-primary":                 "#f1fbe3",
        "on-primary-fixed":           "#394231",
        "on-primary-fixed-variant":   "#555f4c",
        "on-primary-container":       "#4b5543",

        "secondary":                  "#645e57",
        "secondary-dim":              "#58524c",
        "secondary-fixed":            "#ece3da",
        "secondary-fixed-dim":        "#dcd3ca",
        "secondary-container":        "#eae1d8",
        "on-secondary":               "#fff8f2",
        "on-secondary-fixed":         "#433f38",
        "on-secondary-fixed-variant": "#605b54",
        "on-secondary-container":     "#56514a",

        "tertiary":                   "#81543c",
        "tertiary-dim":               "#744931",
        "tertiary-fixed":             "#eeb496",
        "tertiary-fixed-dim":         "#dfa78a",
        "tertiary-container":         "#f5c9ab",
        "on-tertiary":                "#fff7f5",
        "on-tertiary-fixed-variant":  "#643b25",
        "on-tertiary-container":      "#59331d",

        "background":                 "#faf9f8",
        "on-background":              "#2f3333",

        "surface-bright":             "#faf9f8",
        "surface-dim":                "#d6dbda",
        "surface-tint":               "#58614f",
        "surface-variant":            "#dfe3e2",
        "surface-container-lowest":   "#ffffff",
        "surface-container-low":      "#f3f4f3",
        "surface-container":          "#edeeed",
        "surface-container-high":     "#e6e9e8",
        "surface-container-highest":  "#dfe3e2",

        "on-surface":                 "#2f3333",
        "on-surface-variant":         "#5b605f",
        "inverse-surface":            "#0d0e0e",
        "inverse-on-surface":         "#9d9d9c",
        "inverse-primary":            "#e7f2d9",

        "outline":                    "#777c7b",
        "outline-variant":            "#aeb3b2",

        "error":                      "#9e422c",
        "error-dim":                  "#5c1202",
        "error-container":            "#fe8b70",
        "on-error-container":         "#742410",

        // Legacy aliases kept so existing className strings don't break
        page:               "#faf9f8",
        surface:            "#edeeed",
        card:               "#ffffff",
        stat:               "#f3f4f3",
        hover:              "#e6e9e8",
        border:             "#aeb3b2",
        "border-subtle":    "#dfe3e2",
        "border-input":     "#aeb3b2",
        "text-primary":     "#2f3333",
        "text-secondary":   "#645e57",
        "text-muted":       "#777c7b",
        "text-hint":        "#aeb3b2",
        amber:              "#58614f",
        "amber-light":      "#dce6ce",
        "amber-border":     "#ced8c1",
        "score-green":      "#58614f",
        "score-green-bg":   "#dce6ce",
        "score-amber":      "#81543c",
        "score-red":        "#9e422c",
        "score-red-bg":     "#fe8b70",
      },
      boxShadow: {
        card:      "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
        "card-hover": "0px 4px 20px rgba(47,51,51,0.06), 0px 16px 48px rgba(47,51,51,0.09)",
        float:     "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
        ambient:   "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
        focus:     "0 0 0 3px rgba(88,97,79,0.2)",
      },
      borderRadius: {
        DEFAULT: "0.25rem",
        md:  "0.75rem",
        lg:  "0.5rem",
        xl:  "0.75rem",
        "2xl": "1rem",
        full: "9999px",
      },
    },
  },
  plugins: [],
};

export default config;
