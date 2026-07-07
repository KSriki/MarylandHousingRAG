/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Design tokens map to CSS variables (set in index.css) so a light
        // theme can be added later without touching components.
        bg: "hsl(var(--bg))",
        surface: "hsl(var(--surface))",
        "surface-2": "hsl(var(--surface-2))",
        border: "hsl(var(--border))",
        text: "hsl(var(--text))",
        "text-dim": "hsl(var(--text-dim))",
        "text-faint": "hsl(var(--text-faint))",
        accent: "hsl(var(--accent))",
        "accent-dim": "hsl(var(--accent-dim))",
        danger: "hsl(var(--danger))",
      },
      fontFamily: {
        serif: ['Charter', 'Iowan Old Style', 'Georgia', 'serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"SF Mono"', 'Menlo', 'monospace'],
      },
      maxWidth: { reading: "760px" },
    },
  },
  plugins: [],
};
