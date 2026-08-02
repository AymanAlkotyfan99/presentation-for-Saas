import { NextResponse } from "next/server";
import { readUserConfigFile } from "@/lib/user-config-store";

export const dynamic = "force-dynamic";

export async function GET() {
  const userConfigPath = process.env.USER_CONFIG_PATH;
  let fileDisabled: string | undefined;
  let fileEnabled: string | undefined;
  if (userConfigPath) {
    try {
      const parsed = readUserConfigFile<{
        DISABLE_ANONYMOUS_TRACKING?: string;
        ENABLE_ANONYMOUS_TRACKING?: string;
      }>(
        userConfigPath
      );
      fileDisabled = parsed?.DISABLE_ANONYMOUS_TRACKING;
      fileEnabled = parsed?.ENABLE_ANONYMOUS_TRACKING;
    } catch {
      fileDisabled = undefined;
    }
  }
  const envDisabled =
    process.env.DISABLE_ANONYMOUS_TRACKING === "true" ||
    process.env.DISABLE_ANONYMOUS_TRACKING === "True";
  const isDisabled =
    envDisabled ||
    fileDisabled === "true" ||
    fileDisabled === "True";
  const envEnabled =
    process.env.ENABLE_ANONYMOUS_TRACKING === "true" ||
    process.env.ENABLE_ANONYMOUS_TRACKING === "True";
  const isEnabled =
    envEnabled || fileEnabled === "true" || fileEnabled === "True";
  const telemetryEnabled = isEnabled && !isDisabled;
  return NextResponse.json({ telemetryEnabled });
}

