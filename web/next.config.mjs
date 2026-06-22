/** @type {import('next').NextConfig} */
const nextConfig = {
  // The control UI is fully client-side, so export it as a static site. This
  // lets Vercel serve it from web/out without any Root Directory / framework
  // detection (see root vercel.json).
  output: "export",
};

export default nextConfig;
