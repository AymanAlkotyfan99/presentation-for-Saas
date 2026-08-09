import { notFound } from "next/navigation";
import { createCanonicalVisualFixture } from "@/components/editor/fixtures/visual";
import { CanonicalRendererFixtureClient } from "./CanonicalRendererFixtureClient";

export const dynamic = "force-dynamic";

export default function CanonicalRendererFixturePage() {
  if (process.env.NODE_ENV === "production" && process.env.INTERNAL_CANONICAL_RENDERER_FIXTURES_ENABLED !== "true") notFound();
  return <CanonicalRendererFixtureClient document={createCanonicalVisualFixture()} />;
}
