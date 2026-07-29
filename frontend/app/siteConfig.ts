// frontend/app/siteConfig.ts
// Central route registry — import from here instead of hardcoding paths.

export const siteConfig = {
  baseLinks: {
    home:        "/",
    incidents:   "/incidents",
    controls:    "/controls",
    vendors:     "/vendors",
    settings: {
      general: "/settings/general",
      users:   "/settings/users",
    },
  },
} as const