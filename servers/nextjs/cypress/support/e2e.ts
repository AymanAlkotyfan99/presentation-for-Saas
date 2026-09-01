import "./commands";

import { configureAccountLifecycleArtifactSafety } from "./account-lifecycle-artifacts";

configureAccountLifecycleArtifactSafety();

beforeEach(() => {
  // Lifecycle tokens are memory-only. Tests start without browser-persisted
  // values so a failed journey cannot leak a prior test's account material.
  cy.clearCookies({ log: false });
  cy.clearLocalStorage({ log: false });
  cy.window({ log: false }).then((window) => {
    window.sessionStorage.clear();
  });
});
