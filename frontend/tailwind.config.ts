import type { Config } from "tailwindcss";
import daisyui from "daisyui";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./hooks/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto"],
      },
    },
  },
  plugins: [daisyui],
  daisyui: {
    themes: [
      {
        alpharag: {
          primary: "#0ea5e9",
          "primary-content": "#ffffff",
          secondary: "#6366f1",
          accent: "#22d3ee",
          neutral: "#1e293b",
          "base-100": "#0b1220",
          "base-200": "#111a2e",
          "base-300": "#1a2540",
          "base-content": "#e2e8f0",
          info: "#3abff8",
          success: "#36d399",
          warning: "#fbbd23",
          error: "#f87272",
        },
      },
      "light",
    ],
    darkTheme: "alpharag",
    base: true,
    styled: true,
    utils: true,
    logs: false,
  },
};

export default config;
