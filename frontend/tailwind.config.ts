import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ubnt: {
          50: "#eff6ff",
          100: "#dbeafe",
          500: "#006fff",
          600: "#0055cc",
          700: "#003fa3",
          900: "#0b192c",
        },
      },
    },
  },
  plugins: [],
};

export default config;
