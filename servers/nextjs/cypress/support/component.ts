// ***********************************************************
// This example support/component.ts is processed and
// loaded automatically before your test files.
//
// This is a great place to put global configuration and
// behavior that modifies Cypress.
//
// You can change the location of this file or turn off
// automatically serving support files with the
// 'supportFile' configuration option.
//
// You can read more here:
// https://on.cypress.io/configuration
// ***********************************************************

// Import commands.js using ES2015 syntax:
import "./commands";

import axe, { type AxeResults, type RunOptions } from "axe-core";
import { mount } from "cypress/react";

import { configureAccountLifecycleArtifactSafety } from "./account-lifecycle-artifacts";

configureAccountLifecycleArtifactSafety();

// Augment the Cypress namespace to include type definitions for
// your custom command.
// Alternatively, can be defined in cypress/support/component.d.ts
// with a <reference path="./component" /> at the top of your spec.
declare global {
  namespace Cypress {
    interface Chainable {
      mount: typeof mount;
      checkAccountLifecycleAccessibility(options?: RunOptions): Chainable<AxeResults>;
    }
  }
}

Cypress.Commands.add("mount", mount);

Cypress.Commands.add(
  "checkAccountLifecycleAccessibility",
  (options: RunOptions = {}) =>
    cy.document({ log: false }).then(async (document) => {
      const results = await axe.run(document, options);
      const blocking = results.violations.filter(({ impact }) =>
        impact === "critical" || impact === "serious",
      );
      expect(
        blocking,
        blocking.map(({ id, impact }) => `${impact}:${id}`).join(", "),
      ).to.have.length(0);
      return results;
    }),
);

// Example use:
// cy.mount(<MyComponent />)
