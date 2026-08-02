import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";

import {
  MIXPANEL_PROPERTY_BLACKLIST,
  MIXPANEL_PRIVACY_DEFAULTS,
  TELEMETRY_ENABLED_ON_STATUS_FAILURE,
} from "../lib/telemetry-privacy.mjs";
import {
  TELEMETRY_ERROR_CATEGORIES,
  categorizeFileExtension,
  categorizeTelemetryRoute,
  sanitizeAnalyticsError,
  sanitizeTelemetryProperties,
} from "../lib/telemetry-payload-policy.mjs";

test("telemetry status failures fail closed", () => {
  assert.equal(TELEMETRY_ENABLED_ON_STATUS_FAILURE, false);
});

test("product analytics never implicitly enables session replay", () => {
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.record_sessions_percent, 0);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.record_canvas, false);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.record_collect_fonts, false);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.record_mask_text_selector, "*");
  assert.match(MIXPANEL_PRIVACY_DEFAULTS.record_block_selector, /canvas/);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.autocapture, false);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.track_marketing, false);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.store_google, false);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.save_referrer, false);
  assert.equal(MIXPANEL_PRIVACY_DEFAULTS.stop_utm_persistence, true);
  for (const property of [
    "$current_url",
    "$referrer",
    "$initial_referrer",
    "current_page_title",
    "current_url_search",
    "mp_keyword",
    "utm_campaign",
    "gclid",
  ]) {
    assert.ok(MIXPANEL_PROPERTY_BLACKLIST.includes(property), property);
  }
});

test("privacy defaults cannot be mutated at runtime", () => {
  assert.equal(Object.isFrozen(MIXPANEL_PRIVACY_DEFAULTS), true);
  assert.equal(Object.isFrozen(MIXPANEL_PROPERTY_BLACKLIST), true);
});

test("analytics requires explicit consent and an explicit project token", () => {
  const statusRoute = readFileSync(
    new URL("../app/api/telemetry-status/route.ts", import.meta.url),
    "utf8",
  );
  const mixpanelSource = readFileSync(
    new URL("../utils/mixpanel.ts", import.meta.url),
    "utf8",
  );
  assert.match(statusRoute, /ENABLE_ANONYMOUS_TRACKING/);
  assert.match(statusRoute, /isEnabled && !isDisabled/);
  assert.match(mixpanelSource, /process\.env\.NEXT_PUBLIC_MIXPANEL_TOKEN/);
  assert.doesNotMatch(
    mixpanelSource,
    /const\s+MIXPANEL_TOKEN\s*=\s*["'][a-f0-9]{32}["']/i,
  );
});

test("telemetry errors are finite categories and never raw provider text", () => {
  const secretError = new Error(
    "Provider failed for C:\\Clients\\Acme\\Board Strategy.pptx with sk-client-secret",
  );
  assert.equal(sanitizeAnalyticsError(secretError), "unknown");
  assert.equal(
    sanitizeAnalyticsError({ status: 503, message: secretError.message }),
    "server",
  );
  assert.equal(sanitizeAnalyticsError({ statusCode: 401 }), "authentication");
  assert.equal(sanitizeAnalyticsError("Request timed out for client@example.com"), "timeout");
  assert.equal(sanitizeAnalyticsError("429: quota exhausted"), "rate_limited");

  for (const input of [secretError, "Backend returned customer prompt contents"]) {
    const category = sanitizeAnalyticsError(input);
    assert.ok(TELEMETRY_ERROR_CATEGORIES.includes(category));
    assert.doesNotMatch(category, /Acme|\.pptx|sk-|prompt|customer/i);
  }
});

test("the telemetry payload boundary drops content and categorizes metadata", () => {
  const safe = sanitizeTelemetryProperties({
    file_name: "Acme Confidential Board Strategy.pptx",
    file_path: "C:\\Clients\\Acme\\Acme Confidential Board Strategy.pptx",
    template_name: "Acquisition Plan",
    theme_name: "Client Rebrand",
    block_title: "Confidential Restructuring",
    font_url: "https://files.example/client-font.woff2?token=secret",
    provider_label: "Internal Client Provider",
    prompt: "Summarize the unreleased acquisition",
    model: "client-private-model",
    presentation_id: "client-presentation-123",
    nested: { password: "not-for-analytics" },
    unique_tools: ["client_secret_tool"],
    file_size_bytes: 2 * 1024 * 1024,
    error_message:
      "Backend 503 for C:\\Clients\\Acme\\Board Strategy.pptx with sk-secret",
    source: "pptx_upload",
    pathname: "/presentation/client-presentation-123?token=secret",
    to: "https://github.com/presenton/presenton?token=secret",
    status_code: 503,
    has_prompt: true,
    prompt_char_count: 99,
    provider: "openai",
  });

  assert.deepEqual(safe, {
    file_size_bucket: "1MB-5MB",
    error_category: "server",
    source: "pptx_upload",
    route: "presentation",
    to_route: "external",
    status_code: 503,
    has_prompt: true,
    prompt_char_count: 99,
    provider: "openai",
  });
  assert.doesNotMatch(
    JSON.stringify(safe),
    /Acme|Confidential|Strategy|client-font|secret|token=|\.pptx/i,
  );

  const throwing = { source: "pptx_upload" };
  Object.defineProperty(throwing, "file_name", {
    enumerable: true,
    get() {
      throw new Error("getter must not escape");
    },
  });
  assert.deepEqual(sanitizeTelemetryProperties(throwing), {
    source: "pptx_upload",
  });
});

test("file and route helpers expose only bounded categories", () => {
  assert.equal(categorizeFileExtension("C:\\Clients\\Acme Plan.PPTX"), "pptx");
  assert.equal(categorizeFileExtension("secret.env"), "other");
  assert.equal(categorizeFileExtension("README"), "none");
  assert.equal(
    categorizeTelemetryRoute("/presentation/client-id?api_key=secret"),
    "presentation",
  );
  assert.equal(
    categorizeTelemetryRoute("https://client.example/private?token=secret"),
    "external",
  );
});

test("analytics callers do not submit content-derived names or titles", () => {
  const customTemplateSource = readFileSync(
    new URL(
      "../app/(presentation-generator)/custom-template/hooks/useTemplateCreation.ts",
      import.meta.url,
    ),
    "utf8",
  );
  const templatePanelSource = readFileSync(
    new URL(
      "../app/(presentation-generator)/(dashboard)/templates/components/TemplatePanel.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const presentationActionsSource = readFileSync(
    new URL(
      "../app/(presentation-generator)/presentation/components/PresentationActions.tsx",
      import.meta.url,
    ),
    "utf8",
  );
  const mixpanelSource = readFileSync(
    new URL("../utils/mixpanel.ts", import.meta.url),
    "utf8",
  );

  assert.doesNotMatch(customTemplateSource, /file_name\s*:\s*pptxFile\.name/);
  assert.match(customTemplateSource, /categorizeFileExtension\(pptxFile\.name\)/);
  assert.doesNotMatch(templatePanelSource, /template_name\s*:/);
  assert.doesNotMatch(presentationActionsSource, /block_title\s*:/);
  assert.match(mixpanelSource, /sanitizeTelemetryProperties\(props\)/);
  assert.doesNotMatch(
    mixpanelSource,
    /mixpanel\.track\((?:eventName|event),\s*props(?:,|\))/,
  );
});

test("onboarding telemetry consent fails closed and is accurately described", () => {
  const finalStepSource = readFileSync(
    new URL("../components/OnBoarding/FinalStep.tsx", import.meta.url),
    "utf8",
  );
  assert.match(finalStepSource, /data\?\.telemetryEnabled\s*===\s*true/);
  assert.equal(
    finalStepSource.match(/setTrackingEnabled\(false\);\s*setTelemetryEnabled\(false\);/g)
      ?.length,
    2,
  );
  assert.doesNotMatch(finalStepSource, /prev\s*\?\?\s*true/);
  assert.doesNotMatch(finalStepSource, /sharing anonymous usage data/i);
  assert.match(finalStepSource, /limited product-usage events/i);
  assert.match(finalStepSource, /network\/device metadata/i);
  assert.match(finalStepSource, /device identifier/i);
});
