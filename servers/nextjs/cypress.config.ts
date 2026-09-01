import { defineConfig } from "cypress";

export default defineConfig({
  allowCypressEnv: false,
  screenshotOnRunFailure: false,
  video: false,
  e2e: {
    baseUrl: "http://127.0.0.1:3310",
    specPattern: "cypress/e2e/**/*.cy.ts",
    supportFile: "cypress/support/e2e.ts",
  },
  component: {
    devServer: {
      framework: "next",
      bundler: "webpack",
    },
  },
});
