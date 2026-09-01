describe("account lifecycle accessibility harness", () => {
  it("loads axe-core only in Cypress and reports no serious or critical violations", () => {
    cy.document().then((document) => {
      document.documentElement.lang = "en";
      document.documentElement.dir = "ltr";
    });
    cy.mount(
      <main>
        <h1>Account lifecycle test harness</h1>
        <label htmlFor="account-test-email">Email</label>
        <input id="account-test-email" type="email" autoComplete="email" />
        <button type="button">Continue</button>
      </main>,
    );

    cy.checkAccountLifecycleAccessibility();
  });
});
