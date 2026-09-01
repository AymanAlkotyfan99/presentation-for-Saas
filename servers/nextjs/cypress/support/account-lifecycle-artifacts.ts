const ACCOUNT_LIFECYCLE_BLACKOUT_SELECTORS = [
  "[data-account-email]",
  "[data-account-secret]",
  "[data-account-token]",
  'input[type="password"]',
  'input[autocomplete="one-time-code"]',
];

export function configureAccountLifecycleArtifactSafety(): void {
  // Failure screenshots and video are disabled in cypress.config.ts. Explicit
  // screenshots remain available, but account credentials and bearer handoff
  // fields are always blacked out before Cypress writes an image artifact.
  Cypress.Screenshot.defaults({
    blackout: ACCOUNT_LIFECYCLE_BLACKOUT_SELECTORS,
    capture: "viewport",
  });
}
