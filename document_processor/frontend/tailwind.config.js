/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["'IBM Plex Sans'", "sans-serif"]
      },
      colors: {
        ink: "#0E1B2E",
        gold: "#E5B96D",
        slate: "#E7EDF3",
        sky: "#F7FBFF",
        ocean: "#2C517A"
      },
      boxShadow: {
        soft: "0 20px 60px rgba(14, 27, 46, 0.12)"
      },
      backgroundImage: {
        grid: "radial-gradient(circle at 1px 1px, rgba(14,27,46,0.08) 1px, transparent 0)",
        glow: "radial-gradient(circle at top, rgba(229,185,109,0.22), transparent 60%)"
      }
    }
  },
  plugins: []
};
