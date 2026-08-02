import assert from "node:assert/strict";
import test from "node:test";

import { isTrustedSenderUrl } from "../app_dist/ipc/security.js";

const APP_ORIGIN = "http://127.0.0.1:43123";

test("IPC accepts only the exact application origin", () => {
  assert.equal(isTrustedSenderUrl(`${APP_ORIGIN}/presentation/1`, APP_ORIGIN), true);
  assert.equal(isTrustedSenderUrl(`${APP_ORIGIN}/pdf-maker?x=1`, APP_ORIGIN), true);
  assert.equal(isTrustedSenderUrl("http://127.0.0.1:43124/", APP_ORIGIN), false);
  assert.equal(isTrustedSenderUrl("http://localhost:43123/", APP_ORIGIN), false);
  assert.equal(isTrustedSenderUrl("https://127.0.0.1:43123/", APP_ORIGIN), false);
  assert.equal(isTrustedSenderUrl("file:///tmp/index.html", APP_ORIGIN), false);
});

test("lookalike and malformed renderer URLs are rejected", () => {
  assert.equal(
    isTrustedSenderUrl("http://127.0.0.1:43123.evil.example/", APP_ORIGIN),
    false,
  );
  assert.equal(
    isTrustedSenderUrl("http://127.0.0.1:43123@evil.example/", APP_ORIGIN),
    false,
  );
  assert.equal(isTrustedSenderUrl("javascript:alert(1)", APP_ORIGIN), false);
  assert.equal(isTrustedSenderUrl("not a URL", APP_ORIGIN), false);
  assert.equal(isTrustedSenderUrl(APP_ORIGIN, "not a URL"), false);
});
