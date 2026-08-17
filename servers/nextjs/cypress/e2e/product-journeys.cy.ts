/// <reference types="cypress" />

import en from "../../messages/en.json";
import ar from "../../messages/ar.json";

let dashboardResponseMode: "success" | "failure" | "slow" = "success";

const workspace = {
  id: "10000000-0000-4000-8000-000000000001",
  name: "Personal",
  isPersonal: true,
  role: "OWNER",
  permissions: ["workspace:view", "members:view", "presentations:read", "presentations:write"],
  createdAt: "2026-01-01T00:00:00.000Z",
};

function fixturePresentation(id = "presentation-1", title = "Quarterly Strategy") {
  return {
    id,
    version: "v2-standard",
    title,
    created_at: "2026-06-01T09:00:00.000Z",
    updated_at: "2026-06-01T09:00:00.000Z",
    data: null,
    file: "",
    n_slides: 10,
    prompt: "A concise product strategy presentation",
    summary: null,
    theme: null,
    titles: [],
    user_id: "e2e-user",
    vector_store: null,
    thumbnail: "",
    slides: [],
  };
}

function reset() {
  let authenticated = false;
  let presentations = [fixturePresentation()];
  dashboardResponseMode = "success";

  cy.viewport(1280, 800);
  cy.intercept("GET", "**/api/v1/auth/status", (request) => request.reply({
    configured: true,
    authenticated,
    username: authenticated ? "Ayman" : null,
    user_id: authenticated ? "e2e-user" : null,
    role: authenticated ? "user" : null,
    preferred_locale: null,
  }));
  cy.intercept("POST", "**/api/v1/auth/login", (request) => {
    authenticated = true;
    request.reply({
      statusCode: 200,
      headers: { "set-cookie": "bayanly_e2e_session=user; Path=/; HttpOnly; SameSite=Lax" },
      body: { configured: true, authenticated: true, username: "Ayman", user_id: "e2e-user", role: "user" },
    });
  });
  cy.intercept("POST", "**/api/v1/auth/logout", (request) => {
    authenticated = false;
    request.reply({ statusCode: 200, headers: { "set-cookie": "bayanly_e2e_session=; Path=/; Max-Age=0" }, body: {} });
  });
  cy.intercept("PUT", "**/api/v1/auth/preferences/locale", { statusCode: 200, body: {} });
  cy.intercept("GET", "**/api/v1/workspaces/current", workspace);
  cy.intercept("GET", "**/api/v1/workspaces", [workspace]);
  cy.intercept("PUT", "**/api/v1/workspaces/current", workspace);
  cy.intercept("GET", "**/api/v1/ppt/presentation/all*", (request) => {
    if (dashboardResponseMode === "failure") {
      request.destroy();
      return;
    }
    request.reply({
      delay: dashboardResponseMode === "slow" ? 1_000 : 0,
      statusCode: 200,
      body: request.url.includes("version=v1-standard") ? [] : presentations,
    });
  });
  cy.intercept("POST", "**/api/v1/ppt/presentation/create", { id: "outline-handoff" });
  cy.intercept("GET", "**/api/v1/ppt/template/all?page_size=100&default=true", {
    items: [
      {
        id: "executive",
        name: "Executive",
        description: "A polished business presentation template",
        layout_count: 12,
        thumbnail: null,
        is_default: true,
      },
    ],
    total: 1,
    page: 1,
    page_size: 100,
  });
  cy.intercept("GET", "**/api/v1/ppt/template/all?page_size=100&default=false", {
    items: [],
    total: 0,
    page: 1,
    page_size: 100,
  });
  const outlineSlides = Array.from({ length: 10 }, (_, index) => ({
    content:
      index === 0
        ? "## How Artificial Intelligence Is Transforming Education<br>Safer, more personal learning at scale."
        : `## Education shift ${index + 1}<br />Supporting point ${index + 1}`,
  }));
  const outlinePayload = JSON.stringify({ slides: outlineSlides });
  cy.intercept("GET", "**/api/v1/ppt/outlines/stream/outline-handoff", {
    statusCode: 200,
    headers: { "content-type": "text/event-stream" },
    body:
      `event: response\ndata: ${JSON.stringify({ type: "chunk", chunk: outlinePayload })}\n\n` +
      `event: response\ndata: ${JSON.stringify({
        type: "complete",
        presentation: { id: "outline-handoff", outlines: { slides: outlineSlides } },
      })}\n\n`,
  });
  cy.intercept("POST", "**/api/v1/ppt/presentation/prepare", (request) => {
    request.alias = "preparePresentation";
    request.reply({ presentation_id: "outline-handoff" });
  });
  cy.intercept("POST", "**/api/v1/ppt/presentation/create/blank", fixturePresentation("blank-presentation", "Untitled presentation"));
  cy.intercept("GET", /\/api\/v1\/ppt\/presentation\/(?!all(?:[/?]|$))[^/?]+(?:\?.*)?$/, (request) => {
    const id = request.url.split("/").pop()?.split("?")[0];
    request.reply(presentations.find((item) => item.id === id) || { statusCode: 404, body: { detail: "Not found" } });
  });
  cy.intercept("POST", "**/api/v1/ppt/presentation/*/duplicate", (request) => {
    const sourceId = request.url.split("/").at(-2);
    const source = presentations.find((item) => item.id === sourceId) || fixturePresentation();
    const duplicated = { ...source, id: `${source.id}-copy`, title: `${source.title} Copy` };
    presentations = [duplicated, ...presentations];
    request.reply(duplicated);
  });
  cy.intercept("DELETE", "**/api/v1/ppt/presentation/*", (request) => {
    const id = request.url.split("/").pop()?.split("?")[0];
    presentations = presentations.filter((item) => item.id !== id);
    request.reply({ statusCode: 204 });
  });

  cy.request("POST", "http://127.0.0.1:8320/__test/reset");
  cy.clearCookies();
  cy.clearLocalStorage();
}

function login(locale = "en") {
  cy.visit(`/${locale}`);
  const messages = locale === "ar" ? ar : en;
  cy.get("#username", { timeout: 15_000 }).type("ayman");
  cy.get("#password").type("password");
  cy.contains("button", messages.auth.submit).click();
  cy.location("pathname", { timeout: 30_000 }).should("eq", `/${locale}/dashboard`);
  cy.contains(messages.dashboard.welcome.replace("{name}", "Ayman"), { timeout: 30_000 }).should("be.visible");
}

function skipOnboarding(messages = en) {
  cy.get("body").then(($body) => {
    if ($body.find(`[aria-label="${messages.productOnboarding.skip}"]`).length) {
      cy.get(`[aria-label="${messages.productOnboarding.skip}"]`).click();
    }
  });
}

describe("Bayanly product journeys", () => {
  beforeEach(reset);

  it("Journey A — English creation continues through the reviewed outline", () => {
    login("en");
    skipOnboarding();
    cy.get('a[href="/en/create"]').filter(":visible").first().click();
    cy.location("pathname", { timeout: 30_000 }).should("eq", "/en/create");
    cy.get('[data-testid="prompt-input"]').type("A practical launch plan for a sustainable coffee brand");
    cy.get('[data-testid="slides-select"]').click();
    cy.contains('[role="option"]', "10 slides").click();
    cy.get('[data-testid="language-select"]').click();
    cy.contains('[role="option"]', "English").click();
    cy.contains("button", en.preferences.design.business).click();
    cy.get(`[aria-label="${en.preferences.palette.ocean}"]`).click();
    cy.contains("button", en.preferences.images.stock).click();
    cy.contains("button", en.createExperience.outlineAction).click();
    cy.location("pathname", { timeout: 15_000 }).should("eq", "/en/outline");
    cy.get(`[aria-label="${en.templates.openTemplate.replace("{name}", "Executive")}"]`, {
      timeout: 20_000,
    }).click();
    cy.contains(en.outline.slideLabel.replace("{number}", "10"), {
      timeout: 20_000,
    }).should("be.visible");
    cy.contains("How Artificial Intelligence Is Transforming Education").should("be.visible");
    cy.contains("Safer, more personal learning at scale.").should("be.visible");
    cy.contains("<br>").should("not.exist");
    cy.get(`[aria-label="${en.outline.settingsSummary}"]`).within(() => {
      cy.contains("10 slides").should("be.visible");
      cy.contains("English").should("be.visible");
      cy.contains(en.preferences.design.business).should("be.visible");
      cy.contains(en.preferences.palette.ocean).should("be.visible");
      cy.contains("16:9").should("be.visible");
      cy.contains(en.preferences.images.stock).should("be.visible");
    });
    cy.contains("button", en.outline.continue).click();
    cy.wait("@preparePresentation").then(({ request }) => {
      expect(request.body.presentation_id).to.equal("outline-handoff");
      expect(request.body.layout).to.equal("executive");
      expect(request.body.outlines).to.have.length(10);
      expect(JSON.stringify(request.body)).not.to.include("<br");
    });
    cy.location("pathname", { timeout: 20_000 }).should("eq", "/en/presentation");
  });

  it("Journey B — Arabic login, RTL creation, and outline handoff", () => {
    login("ar");
    skipOnboarding(ar);
    cy.get("html").should("have.attr", "dir", "rtl");
    cy.get('a[href="/ar/create"]').filter(":visible").first().click();
    cy.location("pathname", { timeout: 30_000 }).should("eq", "/ar/create");
    cy.get('[data-testid="prompt-input"]').type("خطة إطلاق عملية لمنتج تعليمي رقمي");
    cy.get('[data-testid="language-select"]').click();
    cy.contains('[role="option"]', "Arabic").click();
    cy.contains("button", ar.preferences.design.modern).click();
    cy.contains("button", ar.preferences.images.none).click();
    cy.contains("button", ar.createExperience.outlineAction).click();
    cy.location("pathname", { timeout: 15_000 }).should("eq", "/ar/outline");
  });

  it("Journey C — library open, back, duplicate, and delete", () => {
    login("en");
    skipOnboarding();
    cy.get('a[href="/en/presentations"]').filter(":visible").first().click();
    cy.location("pathname", { timeout: 30_000 }).should("eq", "/en/presentations");
    cy.get(`[aria-label="${en.dashboard.openNamed.replace("{title}", "Quarterly Strategy")}"]`).first().click();
    cy.location("pathname", { timeout: 30_000 }).should("eq", "/en/presentation");
    cy.go("back");
    cy.location("pathname", { timeout: 30_000 }).should("eq", "/en/presentations");

    cy.get(`[aria-label="${en.dashboard.openMenu.replace("{title}", "Quarterly Strategy")}"]`).click();
    cy.contains("button", en.common.duplicate).click();
    cy.contains("Quarterly Strategy Copy").should("be.visible");

    cy.get(`[aria-label="${en.dashboard.openMenu.replace("{title}", "Quarterly Strategy")}"]`).click();
    cy.contains("button", en.common.delete).click();
    cy.get('[role="dialog"]').within(() => cy.contains("button", en.common.delete).click());
    cy.get(`[aria-label="${en.dashboard.openNamed.replace("{title}", "Quarterly Strategy")}"]`).should("not.exist");
  });

  it("Journey D — locale switching preserves the logical destination", () => {
    login("en");
    skipOnboarding();
    cy.get(`select[aria-label="${en.accessibility.changeLanguage}"]`).filter(":visible").first().select("ar");
    cy.location("pathname").should("eq", "/ar/dashboard");
    cy.get("html").should("have.attr", "dir", "rtl");
    cy.get(`select[aria-label="${ar.accessibility.changeLanguage}"]`).filter(":visible").first().select("en");
    cy.location("pathname").should("eq", "/en/dashboard");
  });

  it("Journey E — expired sessions remove protected content", () => {
    login("en");
    cy.clearCookie("bayanly_e2e_session");
    cy.intercept("GET", "**/api/v1/auth/status", {
      configured: true,
      authenticated: false,
      username: null,
      user_id: null,
      role: null,
    });
    cy.document().then((document) => document.dispatchEvent(new Event("visibilitychange")));
    cy.location("pathname", { timeout: 15_000 }).should("eq", "/en");
    cy.location("search").should("include", "reason=session-expired");
    cy.contains(en.auth.sessionExpiredTitle).should("be.visible");
    cy.contains(en.auth.title.replace("{productShortName}", "Bayanly")).should("be.visible");
  });

  it("Journey F — a normal user cannot open platform administration", () => {
    login("en");
    cy.request({ url: "/en/admin/platform", followRedirect: false }).then((response) => {
      const redirectEvidence = `${response.headers.location || ""} ${String(response.body)}`;
      expect(redirectEvidence).to.include("/dashboard");
    });
    cy.contains(en.navigation.admin).should("not.exist");
  });

  it("Journey G — dashboard network failure recovers through retry", () => {
    login("en");
    skipOnboarding();
    cy.then(() => { dashboardResponseMode = "failure"; });
    cy.visit("/en/presentations");
    cy.contains(en.dashboard.loadFailedTitle, { timeout: 20_000 }).should("be.visible");
    cy.then(() => { dashboardResponseMode = "success"; });
    cy.contains("button", en.common.retry).click();
    cy.contains("Quarterly Strategy", { timeout: 20_000 }).should("be.visible");
  });

  it("Journey H — slow dashboard responses show a skeleton and resolve", () => {
    login("en");
    skipOnboarding();
    dashboardResponseMode = "slow";
    cy.visit("/en/presentations");
    cy.get(".animate-pulse").should("exist");
    cy.contains("Quarterly Strategy", { timeout: 20_000 }).should("be.visible");
    cy.get(".animate-pulse").should("not.exist");
  });
});
