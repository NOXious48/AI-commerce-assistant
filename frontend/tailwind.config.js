/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-primary': '#0f1117',
        'bg-secondary': '#1a1d27',
        'bg-card': '#222639',
        'bg-chat': '#161923',
        'accent': '#6c5ce7',
        'accent-light': '#a29bfe',
        'accent-glow': 'rgba(108,92,231,0.3)',
        'text-primary': '#f0f0f5',
        'text-secondary': '#9ca3af',
        'text-muted': '#6b7280',
        'border-light': 'rgba(255,255,255,0.06)',
        'success': '#00b894',
        'warning': '#fdcb6e',
        'card-hover': '#2a2f45',
        'chat-user': '#6c5ce7',
        'chat-ai': '#2d3250',
        'star': '#f9ca24',
        'scrollbar-thumb': '#4b5563',
        'sidebar-bg': '#12141c',
        'sidebar-hover': '#1e2130',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    },
  },
  plugins: [],
}
