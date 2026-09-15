import type { Config } from "eslint";

const config: Config = {
  extends: ["next/core-web-vitals"],
  rules: {
    "react/no-unescaped-entities": "warn",
    "@next/next/no-html-link-for-pages": "off",
    "no-console": ["warn", { allow: ["warn", "error"] }],
  },
  ignorePatterns: ["node_modules", "dist", "build", ".next", "coverage"],
};

export default config;
