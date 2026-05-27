/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef8ff',
          100: '#d9efff',
          500: '#0d5cab',
          700: '#0a457f',
          900: '#05213f',
        },
      },
      boxShadow: {
        soft: '0 10px 35px rgba(15, 45, 80, 0.12)',
      },
    },
  },
  plugins: [],
}
