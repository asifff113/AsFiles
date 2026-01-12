/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "#0a0a0a",
        surface: "#1a1a1a",
        "surface-light": "#2a2a2a",
        glass: "rgba(255, 255, 255, 0.05)",
        "glass-hover": "rgba(255, 255, 255, 0.1)",
        border: "rgba(255, 255, 255, 0.1)",
        primary: "#f26b4c",
        "primary-dark": "#e85a3a",
        secondary: "#6b5cf2",
        "secondary-dark": "#5a4be8",
        accent: "#f2d86b",
        success: "#2cb67d",
        danger: "#c03f2e",
        warning: "#f2b84c",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        display: ["Outfit", "Inter", "system-ui", "sans-serif"],
      },
      animation: {
        blob: "blob 7s infinite",
        "fade-in": "fadeIn 0.5s ease-out forwards",
        "slide-up": "slideUp 0.5s ease-out forwards",
        "glow-pulse": "glow-pulse 2s ease-in-out infinite",
      },
      keyframes: {
        blob: {
          "0%, 100%": { transform: "translate(0px, 0px) scale(1)" },
          "33%": { transform: "translate(30px, -50px) scale(1.1)" },
          "66%": { transform: "translate(-20px, 20px) scale(0.9)" },
        },
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(20px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "glow-pulse": {
          "0%, 100%": { textShadow: "0 0 10px rgba(242, 107, 76, 0)" },
          "50%": { textShadow: "0 0 20px rgba(242, 107, 76, 0.5)" },
        },
      },
      boxShadow: {
        glow: "0 0 20px rgba(242, 107, 76, 0.3)",
        "glow-lg": "0 0 40px rgba(242, 107, 76, 0.4)",
        "glow-cyan": "0 0 30px rgba(34, 211, 238, 0.3)",
      },
    },
  },
  plugins: [],
};

