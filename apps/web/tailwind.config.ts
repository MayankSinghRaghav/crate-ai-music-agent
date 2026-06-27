import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Spotify-dark theme tokens
        spotify: {
          black: "#0A0A0A",
          surface: "#121212",
          elevated: "#181818",
          card: "#1A1A1A",
          border: "#2A2A2A",
          green: "#1DB954",
          greenDark: "#179443",
          text: "#FFFFFF",
          subtle: "#B3B3B3",
          muted: "#727272",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "pop-in": {
          "0%": { opacity: "0", transform: "scale(0.96)" },
          "100%": { opacity: "1", transform: "scale(1)" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
        "pop-in": "pop-in 0.25s ease-out both",
      },
    },
  },
  plugins: [],
};

export default config;
