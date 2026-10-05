import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  images: {
    // Asset previews and report PDFs come from whatever host the API returns; they are plain <img>/<a> links.
    remotePatterns: [],
  },
};

export default withNextIntl(nextConfig);
