import { ipcMain } from "electron";
import { readReadableLocalFile } from "../utils/readable-file-access";
import { assertTrustedIpcSender } from "./security";

export function setupReadFile(trustedOrigin: string) {
  ipcMain.handle("read-file", async (event, filePath: unknown) => {
    try {
      assertTrustedIpcSender(event, trustedOrigin);
      const content = readReadableLocalFile(filePath);
      return { content };
    } catch (error) {
      console.error("Error reading file:", error);
      throw error;
    }
  });
}
