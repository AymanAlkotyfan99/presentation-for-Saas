/**
 * Browser security policy shared by every Next.js route.
 *
 * `unsafe-inline` remains necessary for Next's boot payload and the existing
 * HTML/template renderer. `unsafe-eval` is added for the Next.js development
 * runtime or when a build deliberately enables the legacy executable
 * custom-layout compiler.
 */
export function buildContentSecurityPolicy({ allowUnsafeEval = false } = {}) {
  const scriptSources = [
    "'self'",
    "'unsafe-inline'",
    ...(allowUnsafeEval ? ["'unsafe-eval'"] : []),
    "blob:",
  ];

  return [
  "default-src 'self'",
  "base-uri 'self'",
  "object-src 'none'",
  "frame-ancestors 'none'",
  "frame-src 'none'",
  "form-action 'self'",
  `script-src ${scriptSources.join(" ")}`,
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  "font-src 'self' data: https://fonts.gstatic.com",
  "img-src 'self' blob: data: http: https:",
  "media-src 'self' blob: data: http: https:",
  "connect-src 'self' http: https: ws: wss:",
  "worker-src 'self' blob:",
  "manifest-src 'self'",
  ].join("; ");
}

export const contentSecurityPolicy = buildContentSecurityPolicy({
  allowUnsafeEval:
    process.env.NODE_ENV !== "production" ||
    process.env.NEXT_PUBLIC_ENABLE_UNSAFE_CUSTOM_LAYOUTS === "true",
});

export const securityHeaders = [
  { key: "Content-Security-Policy", value: contentSecurityPolicy },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "X-DNS-Prefetch-Control", value: "off" },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin-allow-popups" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
  },
];
