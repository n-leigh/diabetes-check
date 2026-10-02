/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        cream: "#fbf6ec",
        sand: "#f3e9d6",
        ink: "#1f2a33",
        "ink-muted": "#4f5b66",
        navy: "#063154",
        teal: {
          DEFAULT: "#0b7a85",
          hover: "#08616a",
          light: "#e6f4f5",
        },
        marigold: "#f2a73b",
        coral: "#e8765a",
        border: "#e5dcce",
        status: {
          good: "#2f7d4a",
          "good-bg": "#e4f2e7",
          "good-border": "#bce0c6",
          check: "#a86a0a",
          "check-bg": "#fbeed0",
          "check-border": "#f4d99f",
          doctor: "#b03a2e",
          "doctor-bg": "#f9e1dc",
          "doctor-border": "#f1b8af",
        },
      },
      fontFamily: {
        heading: ["Fraunces", "Georgia", "serif"],
        sans: ['"Source Sans 3"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"IBM Plex Mono"', "monospace"],
      },
      borderRadius: {
        button: "8px",
        card: "12px",
        dialog: "16px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(31, 42, 51, 0.06)",
        elevated: "0 4px 12px rgba(31, 42, 51, 0.08)",
      },
    },
  },
  plugins: [],
};
