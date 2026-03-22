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
        page: "#fefcf8",
        surface: "#f7f5f0",
        card: "#ffffff",
        stat: "#f3efe6",
        hover: "#eee9df",
        // Borders
        border: "#e2ddd5",
        "border-subtle": "#ede9e1",
        "border-input": "#ddd8cf",
        // Text
        "text-primary": "#2c2a24",
        "text-secondary": "#7a786f",
        "text-muted": "#aaa89f",
        "text-hint": "#c9bfb0",
        // Amber accent
        amber: "#b5986a",
        "amber-light": "#fdf8f0",
        "amber-border": "#e0d4bc",
        // Score states
        "score-green": "#5a8c5a",
        "score-green-bg": "#f0f7f0",
        "score-amber": "#b5986a",
        "score-red": "#c05a5a",
        "score-red-bg": "#fdf2f0",
      },
    },
  },
  plugins: [],
};

export default config;
