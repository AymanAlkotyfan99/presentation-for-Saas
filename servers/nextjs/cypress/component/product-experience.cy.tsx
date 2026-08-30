/// <reference types="cypress" />

import { Provider } from "react-redux";
import {
  AppRouterContext,
  type AppRouterInstance,
} from "next/dist/shared/lib/app-router-context.shared-runtime";
import {
  PathnameContext,
  SearchParamsContext,
} from "next/dist/shared/lib/hooks-client-context.shared-runtime";

import {
  PresentationLibraryEmpty,
  PresentationLibraryError,
  PresentationLibrarySkeleton,
} from "@/app/(presentation-generator)/(dashboard)/dashboard/components/PresentationLibraryState";
import { ProductOnboarding } from "@/app/(presentation-generator)/(dashboard)/dashboard/components/ProductOnboarding";
import UploadPage from "@/app/(presentation-generator)/upload/components/UploadPage";
import { AppShell } from "@/components/product-shell/AppShell";
import { I18nProvider } from "@/i18n/catalog";
import en from "@/messages/en.json";
import { WorkspaceProvider } from "@/features/workspaces/WorkspaceProvider";
import UserPreferencesPage from "@/features/preferences/UserPreferencesPage";
import {
  ONBOARDING_STORAGE_KEY,
  PRODUCT_PREFERENCES_STORAGE_KEY,
} from "@/lib/product-preferences";
import { store } from "@/store/store";

const personalWorkspace = {
  id: "10000000-0000-4000-8000-000000000001",
  name: "Personal",
  isPersonal: true,
  role: "OWNER" as const,
  permissions: ["members:view", "members:manage", "presentations:read", "presentations:write"],
  createdAt: new Date(0).toISOString(),
};

function ProductProviders({ children }: { children: React.ReactNode }) {
  return (
    <TestRouter>
      <Provider store={store}>
        <I18nProvider locale="en" messages={en}>{children}</I18nProvider>
      </Provider>
    </TestRouter>
  );
}

const testRouter: AppRouterInstance = {
  back: () => undefined,
  forward: () => undefined,
  refresh: () => undefined,
  push: () => undefined,
  replace: () => undefined,
  prefetch: () => undefined,
};

function TestRouter({ children, pathname = "/en/dashboard" }: { children: React.ReactNode; pathname?: string }) {
  return (
    <AppRouterContext.Provider value={testRouter}>
      <PathnameContext.Provider value={pathname}>
        <SearchParamsContext.Provider value={new URLSearchParams()}>{children}</SearchParamsContext.Provider>
      </PathnameContext.Provider>
    </AppRouterContext.Provider>
  );
}

function stubWorkspaceRequests() {
  cy.window().then((window) => {
    cy.stub(window, "fetch").callsFake(async (input) => {
      const url = String(input);
      const body = url.endsWith("/runtime/capabilities")
        ? { workspaces: true, providerRegistry: false }
        : url.endsWith("/current")
          ? personalWorkspace
          : [personalWorkspace];
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
  });
}

describe("Bayanly consumer product experience", () => {
  beforeEach(() => {
    cy.clearLocalStorage();
  });

  it("keeps the normal shell product-focused and exposes account actions", () => {
    stubWorkspaceRequests();
    cy.mount(
      <TestRouter>
        <I18nProvider locale="en" messages={en}>
          <WorkspaceProvider>
            <AppShell username="Ayman" role="user"><div>Protected product content</div></AppShell>
          </WorkspaceProvider>
        </I18nProvider>
      </TestRouter>,
    );

    cy.contains(en.navigation.dashboard).should("be.visible");
    cy.contains(en.navigation.create).should("be.visible");
    cy.contains(en.navigation.presentations).should("be.visible");
    cy.contains(en.navigation.admin).should("not.exist");
    cy.contains(en.navigation.jobs).should("not.exist");
    cy.get(`[aria-label="${en.navigation.accountMenu}"]`).last().click();
    cy.contains(en.navigation.logout).should("be.visible");
  });

  it("uses an intentional mobile drawer and keeps navigation keyboard-addressable", () => {
    cy.viewport(390, 844);
    stubWorkspaceRequests();
    cy.mount(
      <TestRouter>
        <I18nProvider locale="en" messages={en}>
          <WorkspaceProvider>
            <AppShell username="Ayman" role="user"><div>Mobile product content</div></AppShell>
          </WorkspaceProvider>
        </I18nProvider>
      </TestRouter>,
    );
    cy.get(`[aria-label="${en.navigation.openMenu}"]`).should("be.visible").focus().type("{enter}");
    cy.contains(en.navigation.presentations).should("be.visible");
    cy.document().then((document) => {
      expect(document.documentElement.scrollWidth).to.be.at.most(document.documentElement.clientWidth + 1);
    });
  });

  it("persists product preferences without provider or secret fields", () => {
    cy.mount(<ProductProviders><UserPreferencesPage /></ProductProviders>);
    cy.contains("button", en.preferences.design.academic).click();
    cy.contains("button", en.preferences.images.none).click();
    cy.contains("button", en.preferences.motionReduced).click();
    cy.contains("button", en.preferences.save).click();

    cy.window().then((window) => {
      const saved = JSON.parse(window.localStorage.getItem(PRODUCT_PREFERENCES_STORAGE_KEY) || "{}");
      expect(saved).to.include({ designStyle: "academic", imagePreference: "none", motion: "reduced" });
      expect(JSON.stringify(saved)).not.to.match(/api.?key|provider|redis|storage/i);
    });
  });

  it("makes onboarding skippable and non-blocking", () => {
    cy.mount(<ProductProviders><ProductOnboarding /></ProductProviders>);
    cy.contains(en.productOnboarding.title).should("be.visible");
    cy.get(`[aria-label="${en.productOnboarding.skip}"]`).click();
    cy.contains(en.productOnboarding.title).should("not.exist");
    cy.window().then((window) => {
      expect(window.localStorage.getItem(ONBOARDING_STORAGE_KEY)).to.equal("true");
    });
  });

  it("renders explicit library loading, empty, search-empty, and recoverable error states", () => {
    cy.mount(<ProductProviders><PresentationLibrarySkeleton /></ProductProviders>);
    cy.get(".animate-pulse").should("have.length.at.least", 1);

    cy.mount(<ProductProviders><PresentationLibraryEmpty /></ProductProviders>);
    cy.contains(en.dashboard.emptyTitle).should("be.visible");

    cy.mount(<ProductProviders><PresentationLibraryEmpty searchActive /></ProductProviders>);
    cy.contains(en.dashboard.noResultsTitle).should("be.visible");

    const retry = cy.stub().as("retry");
    cy.mount(<ProductProviders><PresentationLibraryError error="A safe product error" onRetry={retry} /></ProductProviders>);
    cy.contains(en.dashboard.loadFailedTitle).should("be.visible");
    cy.contains("button", en.common.retry).click();
    cy.get("@retry").should("have.been.calledOnce");
  });

  it("captures product-level creation choices without showing infrastructure providers", () => {
    cy.mount(<ProductProviders><UploadPage /></ProductProviders>);
    cy.contains(en.createExperience.title).should("be.visible");
    cy.contains("button", en.preferences.design.business).click();
    cy.contains("button", en.preferences.images.stock).click();
    cy.contains("button", "4:3").click();
    cy.contains("OpenAI").should("not.exist");
    cy.contains("ProviderExecutor").should("not.exist");
    cy.contains("API key").should("not.exist");
  });
});
