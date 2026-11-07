import type { NextConfig } from "next";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectDir = path.dirname(fileURLToPath(import.meta.url));
const nextConfig: NextConfig = { reactStrictMode: true, outputFileTracingRoot: path.resolve(projectDir, "..") };
export default nextConfig;

