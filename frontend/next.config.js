/** @type {import('next').NextConfig} */
module.exports = {
  // Browser validation must not overwrite a running local development build.
  distDir: process.env.E2E_ISOLATED_BUILD === '1' ? '.next-e2e' : '.next',
};
