import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        slateink: "#0f172a",
        cloud: "#f8fafc",
        primary: "#0b5fff",
        accent: "#18a957",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        panel: "0 12px 30px rgba(15,23,42,0.08)",
      },
      keyframes: {
        rise: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" }
        }
      },
      animation: {
        rise: "rise 380ms ease-out"
      }
    },
  },
  plugins: [],
};

export default config;
