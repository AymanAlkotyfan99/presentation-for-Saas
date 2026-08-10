import React from "react";

import { requireAppSession } from "@/utils/serverAuth";
import { ConfigurationInitializer } from "../ConfigurationInitializer";
import { WorkspaceProvider } from "@/features/workspaces/WorkspaceProvider";

export default async function Layout({ children }: { children: React.ReactNode }) {
  await requireAppSession();
  return (
    <div>
      <ConfigurationInitializer><WorkspaceProvider>{children}</WorkspaceProvider></ConfigurationInitializer>
    </div>
  );
}
