/// <reference types="cypress" />

import { CanonicalBrowserSlide } from "@/renderers/browser";
import { CanonicalKonvaStage } from "@/renderers/konva";
import { createCanonicalVisualFixture } from "@/components/editor/fixtures/visual";

describe("canonical renderer parity fixture", () => {
  it("mounts deterministic browser and Konva scenes for the same mixed-direction slide", () => {
    const document = createCanonicalVisualFixture();
    const slide = document.slides[0];
    cy.viewport(1400, 900);
    cy.mount(
      <div style={{ display: "grid", gridTemplateColumns: "640px 640px", gap: 16 }}>
        <div data-testid="browser" style={{ width: 640, height: 360, overflow: "hidden" }}>
          <div style={{ transform: "scale(.5)", transformOrigin: "top left" }}>
            <CanonicalBrowserSlide document={document} slideId={slide.id} />
          </div>
        </div>
        <div data-testid="konva" style={{ width: 640, height: 360 }}>
          <CanonicalKonvaStage document={document} slideId={slide.id} viewport={{ zoom: .5, offsetX: 0, offsetY: 0, containerWidth: 640, containerHeight: 360 }} />
        </div>
      </div>,
    );
    cy.get("[data-testid=browser] [data-renderer=browser]").should("have.attr", "dir", "rtl");
    cy.get("[data-testid=browser] [data-canonical-element-type=text]").should("contain.text", "ARR +24% (Q1)");
    cy.get("[data-testid=browser] [data-canonical-element-type=chart]").should("exist");
    cy.get("[data-testid=browser] [data-canonical-element-type=table]").should("exist");
    cy.get("[data-testid=browser] [data-canonical-element-type=group]").should("exist");
    cy.get("[data-testid=browser] [data-canonical-element-type=shape]").should("have.length", 2);
    cy.get("[data-testid=konva] canvas").should("exist");
    cy.screenshot("canonical-renderer-parity", { capture: "viewport" });
  });
});
