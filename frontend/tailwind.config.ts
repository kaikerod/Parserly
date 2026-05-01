import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        paper: "#f6f6ef",
        ink: "#191916",
        graphite: "#2c2d29",
        fog: "#ebe8dc",
        line: "#d8d3c4",
        moss: "#356b4f",
        mint: "#b8e2c8",
        teal: "#0f766e",
        coral: "#e65f42",
        amber: "#c98210"
      },
      fontFamily: {
        sans: ["Aptos", "Segoe UI", "Helvetica Neue", "sans-serif"],
        display: ["Aptos Display", "Aptos", "Segoe UI", "sans-serif"],
        mono: ["Cascadia Mono", "SFMono-Regular", "Consolas", "monospace"]
      },
      boxShadow: {
        paper: "0 24px 70px rgba(25, 25, 22, 0.12)",
        tool: "0 10px 30px rgba(25, 25, 22, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
