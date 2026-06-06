/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['system-ui', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['ui-monospace', 'Consolas', 'monospace'],
      },
      colors: {
        // Dark-primary construction-oriented palette (system aware via .dark on html)
        hb: {
          bg: '#0f1117',
          surface: '#16171d',
          border: '#2e303a',
          text: '#e5e7eb',
          muted: '#9ca3af',
          accent: '#a5b4fc',
          'accent-weak': '#6366f1',
          success: '#4ade80',
          warn: '#fbbf24',
          danger: '#f87171',
        },
      },
    },
  },
  plugins: [],
}
