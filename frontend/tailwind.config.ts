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
        paper: "#f4f1ea",
        ink: "#121211",
        night: "#0b0b0c",
        graphite: "#1b1b1d",
        fog: "#28262d",
        line: "#3e3948",
        moss: "#8fd75a",
        mint: "#b7ff91",
        teal: "#35e2bd",
        acid: "#45ff73",
        violet: "#6d5dfc",
        lavender: "#a18bff",
        copper: "#c98245",
        coral: "#ff684f",
        amber: "#f0b347"
      },
      fontFamily: {
        sans: ["Aptos", "Segoe UI", "Helvetica Neue", "sans-serif"],
        display: ["Bahnschrift", "Aptos Display", "Aptos", "Segoe UI", "sans-serif"],
        mono: ["Cascadia Mono", "SFMono-Regular", "Consolas", "monospace"]
      },
      boxShadow: {
        paper: "0 28px 90px rgba(0, 0, 0, 0.46)",
        panel: "0 14px 38px rgba(0, 0, 0, 0.28)",
        tool: "0 16px 34px rgba(0, 0, 0, 0.24)",
        glow: "0 0 0 1px rgba(109, 93, 252, 0.28), 0 22px 70px rgba(109, 93, 252, 0.14)",
        acid: "0 0 0 1px rgba(69, 255, 115, 0.24), 0 18px 50px rgba(69, 255, 115, 0.16)"
      }
    }
  },
  plugins: []
};

export default config;
