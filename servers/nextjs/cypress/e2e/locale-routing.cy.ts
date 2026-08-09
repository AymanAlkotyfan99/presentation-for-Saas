describe("localized application shell", () => {
  it("renders English document attributes", () => {
    cy.visit("/en/a-route-that-does-not-exist", { failOnStatusCode: false });
    cy.get("html").should("have.attr", "lang", "en").and("have.attr", "dir", "ltr");
  });

  it("renders Arabic RTL without horizontal shell overflow", () => {
    cy.visit("/ar/a-route-that-does-not-exist", { failOnStatusCode: false });
    cy.get("html").should("have.attr", "lang", "ar").and("have.attr", "dir", "rtl");
    cy.contains("الصفحة غير موجودة");
    cy.document().then((document) => {
      expect(document.documentElement.scrollWidth).to.be.at.most(document.documentElement.clientWidth + 1);
    });
  });

  it("redirects an unprefixed deep link and preserves its query", () => {
    cy.clearCookie("bayanly_locale");
    cy.visit("/a-route-that-does-not-exist?probe=kept", { failOnStatusCode: false });
    cy.location("pathname").should("match", /^\/(en|ar)\/a-route-that-does-not-exist$/);
    cy.location("search").should("equal", "?probe=kept");
  });
});

