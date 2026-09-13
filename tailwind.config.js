/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/js/**/*.js",
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ["Outfit", "Plus Jakarta Sans", "sans-serif"],
        heading: ["Plus Jakarta Sans", "sans-serif"],
        body: ["Inter", "sans-serif"],
      },
      keyframes: {
        borderSpin: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        borderSweep: {
          "0%": { transform: "rotate(0deg)" },
          "100%": { transform: "rotate(360deg)" },
        },
        floatOrb1: {
          "0%": { transform: "translate(0px, 0px) scale(1)" },
          "50%": { transform: "translate(35px, -25px) scale(1.08)" },
          "100%": { transform: "translate(-25px, 20px) scale(0.95)" },
        },
        floatOrb2: {
          "0%": { transform: "translate(0px, 0px) scale(1)" },
          "50%": { transform: "translate(-30px, 30px) scale(1.1)" },
          "100%": { transform: "translate(25px, -20px) scale(0.92)" },
        },
        floatOrb3: {
          "0%": { transform: "translate(0px, 0px) scale(1)" },
          "50%": { transform: "translate(20px, 35px) scale(1.05)" },
          "100%": { transform: "translate(-25px, -25px) scale(1.08)" },
        },
        pulseGlow: {
          "0%, 100%": { opacity: "0.25", transform: "scale(1)" },
          "50%": { opacity: "0.45", transform: "scale(1.06)" },
        },
        gradientShift: {
          "0%": { backgroundPosition: "0% 50%" },
          "50%": { backgroundPosition: "100% 50%" },
          "100%": { backgroundPosition: "0% 50%" },
        },
        pageReveal: {
          "0%": { opacity: "0", transform: "translateY(12px) scale(0.988)", filter: "blur(2px)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)", filter: "blur(0)" },
        },
        logoBreath: {
          "0%": { transform: "scale(1)" },
          "100%": { transform: "scale(1.06)" },
        },
        logoGlowPulse: {
          "0%": { opacity: "0.65", transform: "scale(0.98)" },
          "100%": { opacity: "1", transform: "scale(1.08)" },
        },
        disclaimerEnter: {
          "0%": { opacity: "0", transform: "translateY(10px) scale(0.98)" },
          "100%": { opacity: "1", transform: "translateY(0) scale(1)" },
        },
      },
      animation: {
        borderSweep: "borderSweep 3.6s linear infinite",
        floatOrb1: "floatOrb1 10s ease-in-out infinite alternate",
        floatOrb2: "floatOrb2 14s ease-in-out infinite alternate",
        floatOrb3: "floatOrb3 12s ease-in-out infinite alternate",
        pulseGlow: "pulseGlow 6s ease-in-out infinite",
        gradientShift: "gradientShift 14s ease infinite",
        pageReveal: "pageReveal var(--page-transition-duration) var(--page-transition-ease) both",
        logoBreath: "logoBreath var(--page-transition-duration) ease-in-out infinite alternate",
        logoGlowPulse: "logoGlowPulse var(--page-transition-duration) ease-in-out infinite alternate",
        disclaimerEnter: "disclaimerEnter 180ms ease-out both",
      },
    },
  },
  plugins: [],
};
