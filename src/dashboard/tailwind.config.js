/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#e8eef5",
          100: "#c5d4e7",
          200: "#9db7d6",
          300: "#7099c5",
          400: "#4f81b8",
          500: "#2e6aab",
          600: "#245e9e",
          700: "#1a4e8a",
          800: "#1e3a5f",
          900: "#122440",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
