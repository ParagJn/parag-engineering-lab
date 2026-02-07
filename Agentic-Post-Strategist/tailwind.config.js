/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        studio: {
          50: "#f1f6fb",
          100: "#dbe8f4",
          200: "#b3cce2",
          300: "#88accd",
          400: "#618fb8",
          500: "#496f95",
          600: "#3b5775",
          700: "#304761",
          800: "#2a3b50",
          900: "#253243"
        }
      },
      boxShadow: {
        panel: "0 18px 45px rgba(17, 31, 51, 0.18)"
      }
    }
  },
  plugins: []
};
