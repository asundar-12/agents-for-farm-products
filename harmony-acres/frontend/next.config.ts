import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pin the workspace root to this app. Without it, a stray package-lock.json in
  // a parent directory (e.g. the home folder) makes Next infer the wrong root
  // and warn on every build.
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
