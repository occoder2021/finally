import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: {
          plane: "#0d1117",
          panel: "#121722",
          raised: "#171d2b",
          overlay: "#1b2233",
        },
        line: {
          DEFAULT: "#232a3b",
          subtle: "#1a2030",
        },
        ink: {
          primary: "#e7e9f0",
          secondary: "#8d95ab",
          muted: "#565f75",
        },
        accent: {
          DEFAULT: "#ecad0a",
          dim: "#8a6c19",
        },
        blue: {
          DEFAULT: "#209dd7",
          dim: "#1a5a78",
        },
        purple: {
          DEFAULT: "#753991",
          hover: "#8a459f",
        },
        good: {
          DEFAULT: "#17c964",
          text: "#3ddc84",
          dim: "#123a24",
        },
        critical: {
          DEFAULT: "#e5484d",
          text: "#ff6b70",
          dim: "#3a1516",
        },
      },
      fontFamily: {
        sans: ["var(--font-ui)", "system-ui", "sans-serif"],
        mono: ["var(--font-data)", "ui-monospace", "monospace"],
      },
      fontSize: {
        micro: ["0.6875rem", { lineHeight: "1rem", letterSpacing: "0.01em" }],
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset",
      },
      keyframes: {
        "flash-up": {
          "0%": { backgroundColor: "rgba(23,201,100,0.35)" },
          "100%": { backgroundColor: "rgba(23,201,100,0)" },
        },
        "flash-down": {
          "0%": { backgroundColor: "rgba(229,72,77,0.35)" },
          "100%": { backgroundColor: "rgba(229,72,77,0)" },
        },
      },
      animation: {
        "flash-up": "flash-up 550ms ease-out",
        "flash-down": "flash-down 550ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
