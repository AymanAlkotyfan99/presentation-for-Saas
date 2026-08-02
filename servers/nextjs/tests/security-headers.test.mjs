import assert from "node:assert/strict";
import test from "node:test";

import {
  buildContentSecurityPolicy,
  contentSecurityPolicy,
  securityHeaders,
} from "../lib/security-headers.mjs";
import nextConfig from "../next.config.mjs";

function headerValue(name) {
  return securityHeaders.find(({ key }) => key === name)?.value;
}

test("CSP blocks high-risk embedding and plugin boundaries", () => {
  assert.match(contentSecurityPolicy, /default-src 'self'/);
  assert.match(contentSecurityPolicy, /object-src 'none'/);
  assert.match(contentSecurityPolicy, /frame-ancestors 'none'/);
  assert.match(contentSecurityPolicy, /frame-src 'none'/);
  assert.match(contentSecurityPolicy, /base-uri 'self'/);
  assert.match(contentSecurityPolicy, /form-action 'self'/);
});

test("default CSP does not permit dynamic code execution", () => {
  const scriptDirective = contentSecurityPolicy
    .split("; ")
    .find((directive) => directive.startsWith("script-src "));

  assert.ok(scriptDirective);
  assert.match(scriptDirective, /'unsafe-inline'/);
  assert.doesNotMatch(scriptDirective, /'unsafe-eval'/);
  assert.doesNotMatch(scriptDirective, /\shttps:\s/);
  assert.doesNotMatch(scriptDirective, /\shttp:\s/);
  assert.doesNotMatch(scriptDirective, /cdn\.jsdelivr\.net/);
  assert.doesNotMatch(scriptDirective, /cdn\.tailwindcss\.com/);
});

test("unsafe-eval requires the explicit legacy custom-layout opt-in", () => {
  const optedIn = buildContentSecurityPolicy({ allowUnsafeEval: true });
  assert.match(optedIn, /script-src[^;]*'unsafe-eval'/);
});

test("defense-in-depth response headers are present", () => {
  assert.equal(headerValue("X-Content-Type-Options"), "nosniff");
  assert.equal(headerValue("X-Frame-Options"), "DENY");
  assert.equal(
    headerValue("Referrer-Policy"),
    "strict-origin-when-cross-origin"
  );
  assert.match(headerValue("Permissions-Policy") ?? "", /camera=\(\)/);
  assert.match(headerValue("Permissions-Policy") ?? "", /microphone=\(\)/);
});

test("Next applies the policy to every route", async () => {
  const routes = await nextConfig.headers();
  assert.equal(routes.length, 1);
  assert.equal(routes[0].source, "/:path*");
  assert.deepEqual(routes[0].headers, securityHeaders);
});
