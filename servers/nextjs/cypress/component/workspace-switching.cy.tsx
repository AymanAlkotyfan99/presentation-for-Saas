/// <reference types="cypress" />

import en from "@/messages/en.json";
import { I18nProvider } from "@/i18n/catalog";
import { WorkspaceProvider, useWorkspace } from "@/features/workspaces/WorkspaceProvider";
import { WorkspaceSwitcher } from "@/features/workspaces/WorkspaceSwitcher";

const personal = {
  id: "10000000-0000-4000-8000-000000000001",
  name: "Personal",
  isPersonal: true,
  role: "OWNER" as const,
  permissions: ["members:view", "members:manage", "presentations:read"],
  createdAt: new Date(0).toISOString(),
};
const team = {
  id: "20000000-0000-4000-8000-000000000002",
  name: "Team",
  isPersonal: false,
  role: "VIEWER" as const,
  permissions: ["members:view", "presentations:read"],
  createdAt: new Date(0).toISOString(),
};

function CapabilityProbe() {
  const workspace = useWorkspace();
  return <button disabled={!workspace.can("members:manage")}>Manage members</button>;
}

describe("workspace switching and permission UI", () => {
  it("switches through the validated server endpoint and remounts with new capabilities", () => {
    cy.window().then((window) => {
      cy.stub(window, "fetch").callsFake(async (_input, init) => {
        if (init?.method === "PUT") return new Response(JSON.stringify(team), { status: 200, headers: { "Content-Type": "application/json" } });
        const url = String(_input);
        const body = url.endsWith("/current") ? personal : [personal, team];
        return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
      });
    });
    cy.mount(
      <I18nProvider locale="en" messages={en}>
        <WorkspaceProvider>
          <WorkspaceSwitcher />
          <CapabilityProbe />
        </WorkspaceProvider>
      </I18nProvider>,
    );
    cy.get("#workspace-switcher").should("have.value", personal.id);
    cy.contains("button", "Manage members").should("not.be.disabled");
    cy.get("#workspace-switcher").select(team.id);
    cy.get("#workspace-switcher").should("have.value", team.id);
    cy.contains("button", "Manage members").should("be.disabled");
    cy.window().its("fetch").should("have.been.calledWithMatch", Cypress.sinon.match.any, Cypress.sinon.match({ method: "PUT" }));
  });
});
