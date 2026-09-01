import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import {
  ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS,
  ACCOUNT_LIFECYCLE_REDACTED_EMAIL,
  ACCOUNT_LIFECYCLE_REDACTED_VALUE,
  assertSecretSafeAccountLifecycleFixture,
  loadAccountLifecycleFixture,
  redactAccountLifecycleArtifact,
} from "./helpers/account-lifecycle.mjs";

for (const locale of ["en", "ar"]) {
  test(`${locale} account lifecycle fixture is reserved and secret-safe`, () => {
    const fixture = loadAccountLifecycleFixture(locale);

    assert.equal(fixture.locale, locale);
    assert.doesNotThrow(() => assertSecretSafeAccountLifecycleFixture(fixture));
    assert.match(fixture.mailbox.messages[0].recipient, /@example\.test$/);
    assert.equal(fixture.mailbox.messages[0].token, ACCOUNT_LIFECYCLE_REDACTED_VALUE);
    assert.match(fixture.mailbox.messages[0].actionUrl, /^\/(en|ar)\/verify#token=\[REDACTED\]$/);
  });
}

test("account lifecycle diagnostics default to no screenshots, video, or traces", () => {
  assert.equal(Object.isFrozen(ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS), true);
  assert.equal(Object.isFrozen(ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS.redactSelectors), true);
  assert.equal(ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS.screenshotOnRunFailure, false);
  assert.equal(ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS.video, false);
  assert.equal(ACCOUNT_LIFECYCLE_ARTIFACT_DEFAULTS.trace, false);

  const diagnostic = redactAccountLifecycleArtifact({
    recipient: "account-en-001@example.test",
    token: "opaque-test-token",
    actionUrl: "/en/verify#token=opaque-test-token",
    outcome: "accepted",
  });
  assert.deepEqual(diagnostic, {
    recipient: ACCOUNT_LIFECYCLE_REDACTED_EMAIL,
    token: ACCOUNT_LIFECYCLE_REDACTED_VALUE,
    actionUrl: ACCOUNT_LIFECYCLE_REDACTED_VALUE,
    outcome: "accepted",
  });

  const cypressConfig = readFileSync(
    new URL("../cypress.config.ts", import.meta.url),
    "utf8",
  );
  const e2eSupport = readFileSync(
    new URL("../cypress/support/e2e.ts", import.meta.url),
    "utf8",
  );
  const componentSupport = readFileSync(
    new URL("../cypress/support/component.ts", import.meta.url),
    "utf8",
  );
  const artifactSafety = readFileSync(
    new URL("../cypress/support/account-lifecycle-artifacts.ts", import.meta.url),
    "utf8",
  );
  assert.match(cypressConfig, /screenshotOnRunFailure:\s*false/);
  assert.match(cypressConfig, /video:\s*false/);
  assert.match(cypressConfig, /supportFile:\s*"cypress\/support\/e2e\.ts"/);
  assert.match(e2eSupport, /configureAccountLifecycleArtifactSafety\(\)/);
  assert.match(componentSupport, /configureAccountLifecycleArtifactSafety\(\)/);
  assert.match(artifactSafety, /Cypress\.Screenshot\.defaults/);
  assert.match(artifactSafety, /data-account-token/);
  assert.match(artifactSafety, /input\[type="password"\]/);
});
