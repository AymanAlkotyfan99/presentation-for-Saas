import { setupExportHandlers } from "./export_handlers";
import { setupReadFile } from "./read_file";

export function setupIpcHandlers(trustedOrigin: string) {
  setupExportHandlers(trustedOrigin);
  setupReadFile(trustedOrigin);
}
