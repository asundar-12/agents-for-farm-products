import type { MetadataRoute } from "next";

// Web app manifest. Next serves this at /manifest.webmanifest automatically
// (it's a special file name), which makes the app installable to a phone's home
// screen and gives it a name, colors, and icon when launched standalone.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Farm Product Agent",
    short_name: "Farm Order",
    description: "Order your weekly farm delivery.",
    start_url: "/dashboard",
    display: "standalone",
    background_color: "#ffffff",
    theme_color: "#16a34a",
    icons: [
      { src: "/icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any" },
      { src: "/favicon.ico", sizes: "48x48", type: "image/x-icon" },
    ],
  };
}
