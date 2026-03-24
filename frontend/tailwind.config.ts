import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["DM Sans", "system-ui", "sans-serif"],
      },
      colors: {
        // Backgrounds
        page: "#faf9f7",
        surface: "#f2efe9",
        card: "#ffffff",
        stat: "#eeebe3",
        hover: "#e8e5dc",
        // Borders
        border: "#e0dcd3",
        "border-subtle": "#ebe7df",
        "border-input": "#d6d1c7",
        // Text
        "text-primary": "#1a1918",
        "text-secondary": "#6b6862",
        "text-muted": "#969288",
        "text-hint": "#c2beb2",
        // Accent — charcoal only, no amber
        amber: "#1a1918",
        "amber-light": "#f2efe9",
        "amber-border": "#d2cdbe",
        // Score states
        "score-green": "#4a7a4a",
        "score-green-bg": "#edf5ed",
        "score-amber": "#a8895b",
        "score-red": "#b34e4e",
        "score-red-bg": "#faebeb",
      },
      boxShadow: {
        'card': '0 2px 8px -2px rgba(26, 25, 24, 0.04), 0 4px 16px -4px rgba(26, 25, 24, 0.03)',
        'card-hover': '0 4px 12px -2px rgba(26, 25, 24, 0.06), 0 8px 24px -6px rgba(26, 25, 24, 0.04)',
        'float': '0 12px 32px -8px rgba(26, 25, 24, 0.08)',
        'focus': '0 0 0 3px rgba(26, 25, 24, 0.1)',
      },
      borderRadius: {
        'xl': '0.75rem',
        '2xl': '1rem',
      }
    },
  },
  plugins: [],
};

export default config;
