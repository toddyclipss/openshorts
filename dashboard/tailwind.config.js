/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Lumen · Studio White — values mirror tokens.css (kept literal so
        // Tailwind alpha modifiers like bg-brass/10 compile)
        paper: "oklch(100% 0 0 / <alpha-value>)",
        paper2: "oklch(98.5% 0.003 260 / <alpha-value>)",
        paper3: "oklch(94.5% 0.005 260 / <alpha-value>)",
        ink: "oklch(14% 0.008 260 / <alpha-value>)",
        ink2: "oklch(28% 0.012 260 / <alpha-value>)",
        muted: "oklch(50% 0.015 260 / <alpha-value>)",
        brass: "oklch(55% 0.15 52 / <alpha-value>)",
        brassink: "oklch(100% 0 0 / <alpha-value>)",
        coral: "oklch(52% 0.19 25 / <alpha-value>)",
        ok: "oklch(50% 0.13 145 / <alpha-value>)",
        warn: "oklch(50% 0.14 65 / <alpha-value>)",
        danger: "oklch(52% 0.20 25 / <alpha-value>)",
        // legacy aliases so untouched files degrade gracefully
        background: "oklch(100% 0 0 / <alpha-value>)",
        surface: "oklch(98.5% 0.003 260 / <alpha-value>)",
        primary: "oklch(55% 0.15 52 / <alpha-value>)",
        accent: "oklch(52% 0.19 25 / <alpha-value>)",
      },
      fontFamily: {
        display: "var(--font-display)",
        body: "var(--font-body)",
        sans: "var(--font-body)",
        serif: "var(--font-display)",
        mono: "var(--font-mono)",
      },
      borderColor: {
        rule: "var(--color-rule)",
        rule2: "var(--color-rule-2)",
      },
      borderRadius: {
        card: "var(--radius-card)",
        input: "var(--radius-input)",
      },
      fontSize: {
        micro: ["10.5px", { letterSpacing: "0.10em" }],
      },
      transitionTimingFunction: {
        out: "var(--ease-out)",
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade': 'fadeIn 0.4s var(--ease-out)',
        // mobile shell: the nav drawer flies in from the edge, sheets rise
        'slide-in-left': 'slideInLeft 0.24s var(--ease-out)',
        'sheet-up': 'sheetUp 0.26s var(--ease-out)',
      },
      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideInLeft: {
          from: { transform: 'translateX(-100%)' },
          to: { transform: 'translateX(0)' },
        },
        sheetUp: {
          from: { transform: 'translateY(12px)', opacity: '0' },
          to: { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [],
}
