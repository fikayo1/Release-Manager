/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async redirects() {
    // Compatibility aliases: refresh- and bookmark-safe (307) forwards to the
    // canonical settings routes.
    return [
      { source: '/github', destination: '/settings/github', permanent: false },
      { source: '/schedule', destination: '/settings/schedule', permanent: false },
    ];
  },
};
export default nextConfig;
