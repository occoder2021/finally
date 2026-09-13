/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "export",
  images: {
    unoptimized: true,
  },
  // Static export cannot rewrite at request time; API calls are same-origin
  // `/api/*` paths handled by the fetch layer in lib/api.ts, not by Next.
  trailingSlash: false,
};

module.exports = nextConfig;
