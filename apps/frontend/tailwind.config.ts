import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0f172a",
        accent: "#f97316",
        panel: "#111827",
        mist: "#cbd5e1",
      },
      fontFamily: {
        display: ["'Segoe UI'", "sans-serif"],
      },
      boxShadow: {
        glow: "0 18px 60px rgba(249, 115, 22, 0.18)",
      },
    },
  },
  plugins: [],
} satisfies Config;

