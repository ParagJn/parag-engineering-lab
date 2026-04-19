/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./public/**/*.{html,js}"],
  theme: {
    extend: {
      colors: {
        google: {
          blue: "#4285F4",
          red: "#EA4335",
          yellow: "#FBBC05",
          green: "#34A853",
        },
      },
    },
  },
  plugins: [],
};
