/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  async redirects() {
    // Compatibility aliases: refresh- and bookmark-safe (307) forwards from the
    // legacy top-level routes to their new `/dashboard/...` homes.
    return [
      { source: '/github', destination: '/dashboard/settings/github', permanent: false },
      { source: '/schedule', destination: '/dashboard/settings/schedule', permanent: false },
      { source: '/releases', destination: '/dashboard/releases', permanent: false },
      { source: '/releases/:id', destination: '/dashboard/releases/:id', permanent: false },
      { source: '/operations', destination: '/dashboard/operations', permanent: false },
      { source: '/settings/github', destination: '/dashboard/settings/github', permanent: false },
      { source: '/settings/schedule', destination: '/dashboard/settings/schedule', permanent: false },
    ];
  },
};
export default nextConfig;
