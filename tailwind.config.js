/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        cream: "#f1fafb",
        sand: "#d9eff3",
        ink: "#1f2a33",
        "ink-muted": "#4f5b66",
        navy: "#014c5e",
        teal: {
          DEFAULT: "#2e7283",
          hover: "#245e6d",
          light: "#e8f5f7",
        },
        marigold: "#f2a73b",
        coral: "#e8765a",
        border: "#b8dce5",
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
