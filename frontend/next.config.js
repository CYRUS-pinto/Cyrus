/** @type {import('next').NextConfig} */
const nextConfig = {
  // Allow images from MinIO and Supabase Storage
  images: {
    remotePatterns: [
      { protocol: "http", hostname: "localhost", port: "9000" },
      { protocol: "https", hostname: "*.supabase.co" },
    ],
  },

  // API proxy — frontend calls /api/... which proxies to FastAPI backend
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },

  // Required for PWA
  reactStrictMode: true,
};

module.exports = nextConfig;
