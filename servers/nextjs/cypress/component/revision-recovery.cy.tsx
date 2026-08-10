/// <reference types="cypress" />

import { RevisionAutosaveController } from "@/features/presentations/persistence/autosave-controller";
import { MemoryRevisionJournal } from "@/features/presentations/persistence/journal";
import { RevisionClient } from "@/features/presentations/persistence/revision-client";

const command = {
  commandId: "cypress-recovery-1",
  type: "UPDATE_SLIDE",
  targetIds: ["10000000-0000-4000-8000-000000000001"],
  payload: { changes: { title: "Recovered" } },
};

describe("revision persistence and recovery", () => {
  it("keeps offline commands durable and acknowledges them only after a server revision", () => {
    cy.wrap((async () => {
      const journal = new MemoryRevisionJournal();
      let online = false;
      const client = new RevisionClient(async () => {
        if (!online) throw new TypeError("offline");
        return new Response(JSON.stringify({
          revision: 2,
          parentRevision: 1,
          checksum: "a".repeat(64),
          source: "command",
          replayed: false,
          document: { presentationId: "p", slides: [] },
          createdAt: new Date().toISOString(),
        }), { status: 200, headers: { "Content-Type": "application/json" } });
      });
      const controller = new RevisionAutosaveController(
        "p", "user:test", 1, journal, client, () => true, undefined, 60_000,
      );
      controller.setOnline(false);
      await controller.enqueue(command);
      await controller.flush();
      expect(controller.getSnapshot().status).to.equal("offline");
      expect(await journal.list("p", "user:test")).to.have.length(1);
      online = true;
      controller.setOnline(true);
      await controller.flush();
      expect(controller.getSnapshot().status).to.equal("saved");
      expect(controller.getSnapshot().acknowledgedRevision).to.equal(2);
      expect(await journal.list("p", "user:test")).to.have.length(0);
      controller.dispose();
    })()).then(() => undefined);
  });
});
