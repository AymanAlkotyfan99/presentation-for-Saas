import { I18nProvider } from "@/i18n/catalog";
import { ProviderRegistryPanel } from "@/features/providers/ProviderRegistryPanel";
import ar from "@/messages/ar.json";
import en from "@/messages/en.json";

const account = {
  id: "00000000-0000-4000-8000-000000000101",
  adapterId: "text.custom",
  name: "Controlled text",
  defaultModel: "controlled-v1",
  safeConfig: { base_url: "https://provider.example/v1" },
  regionPolicyStatus: "ALLOWED" as const,
  enabled: true,
  emergencyDisabled: false,
  hasSecret: true,
  maskedSecret: "••••••••",
  capabilities: [{
    id: "00000000-0000-4000-8000-000000000201",
    family: "TEXT" as const,
    model: "controlled-v1",
    enabled: true,
    metadata: {},
  }],
  health: {
    status: "HEALTHY" as const,
    latencyMs: 12,
    safeErrorCode: null,
    checkedAt: "2026-08-11T12:00:00Z",
  },
};

function interceptReads() {
  cy.intercept("GET", "**/api/v1/providers/adapters", [{
    adapterId: "text.custom",
    family: "TEXT",
    models: ["default"],
    metadata: { secretRequired: true, liveConnectionTest: true },
  }]).as("adapters");
  cy.intercept("GET", "**/api/v1/providers/accounts", [account]).as("accounts");
  cy.intercept("GET", "**/api/v1/providers/routing-policies/TEXT", {
    family: "TEXT",
    priority_account_ids: [account.id],
    allow_fallback: false,
    max_fallbacks: 0,
    version: 1,
  }).as("policy");
}

describe("provider registry settings", () => {
  it("uses the authenticated API contract for accounts, secrets, policy, and health", () => {
    interceptReads();
    cy.intercept("PATCH", `**/api/v1/providers/accounts/${account.id}`, (request) => {
      if (request.body.emergencyDisabled === true) {
        expect(request.body).to.deep.equal({ emergencyDisabled: true });
        request.reply({ ...account, emergencyDisabled: true });
        return;
      }
      expect(request.body).to.deep.include({
        defaultModel: "controlled-v2",
        capabilityModels: ["controlled-v2"],
        enabled: true,
      });
      expect(request.body).not.to.have.property("secret");
      request.reply({ ...account, defaultModel: "controlled-v2" });
    }).as("updateAccount");
    cy.intercept("PUT", `**/api/v1/providers/accounts/${account.id}/secret`, (request) => {
      expect(request.body).to.deep.equal({ secret: "rotated-controlled-secret" });
      request.reply({ statusCode: 204 });
    }).as("rotateSecret");
    cy.intercept("PUT", `**/api/v1/providers/accounts/${account.id}/capabilities/${account.capabilities[0].id}`, (request) => {
      expect(request.body).to.deep.equal({ enabled: false });
      request.reply({ id: account.capabilities[0].id, enabled: false });
    }).as("capability");
    cy.intercept("POST", `**/api/v1/providers/accounts/${account.id}/connection-tests`, {
      statusCode: 202,
      body: { jobId: "00000000-0000-4000-8000-000000000301", replayed: false },
    }).as("connectionTest");
    cy.intercept("POST", "**/api/v1/providers/routing-policies/simulate", (request) => {
      expect(request.body).to.deep.equal({ family: "TEXT", pinnedAccountId: account.id });
      request.reply({
        candidates: [{ accountId: account.id, adapterId: account.adapterId, model: account.defaultModel, fallbackIndex: 0 }],
        exclusions: {},
        policyVersion: 1,
      });
    }).as("simulate");
    cy.intercept("POST", "**/api/v1/providers/accounts", (request) => {
      expect(request.body).to.deep.include({
        adapterId: "text.custom",
        name: "New controlled account",
        defaultModel: "new-model",
        capabilityModels: ["new-model"],
        secret: "new-controlled-secret",
      });
      request.reply({ statusCode: 201, body: account });
    }).as("createAccount");

    cy.mount(<I18nProvider locale="en" messages={en}><ProviderRegistryPanel /></I18nProvider>);
    cy.wait(["@adapters", "@accounts", "@policy"]);
    cy.contains("AI provider registry").should("be.visible");
    cy.contains("Healthy").should("be.visible");

    cy.get("article input[type=password]").should("have.value", "").and("have.attr", "placeholder", account.maskedSecret);
    cy.get('article input[aria-label="Default model"]').clear().type("controlled-v2");
    cy.get('article input[aria-label^="Capability models"]').clear().type("controlled-v2");
    cy.contains("button", "Save account configuration").click();
    cy.wait("@updateAccount");

    cy.get("article input[type=checkbox]").last().uncheck();
    cy.wait("@capability");
    cy.get("article input[type=password]").type("rotated-controlled-secret");
    cy.contains("button", "Rotate").click();
    cy.wait("@rotateSecret");
    cy.contains("button", "Queue connection test").click();
    cy.wait("@connectionTest");
    cy.contains("button", "Emergency disable").click();
    cy.wait("@updateAccount");
    cy.contains("button", "Simulate route").click();
    cy.wait("@simulate");
    cy.contains("text.custom · controlled-v1").should("be.visible");

    cy.get('input[placeholder="Account name"]').type("New controlled account");
    cy.get('input[placeholder="Model or capability"]').clear().type("new-model");
    cy.get('input[placeholder="Provider secret (required)"]').type("new-controlled-secret");
    cy.contains("button", "Create account").click();
    cy.wait("@createAccount");
  });

  it("renders the Arabic catalog using logical automatic direction", () => {
    interceptReads();
    cy.mount(<I18nProvider locale="ar" messages={ar}><ProviderRegistryPanel /></I18nProvider>);
    cy.wait(["@adapters", "@accounts", "@policy"]);
    cy.contains(ar.providers.title).should("be.visible");
    cy.get('div[dir="auto"]').should("exist");
  });
});
