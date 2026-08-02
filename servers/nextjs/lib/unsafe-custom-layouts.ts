export const UNSAFE_CUSTOM_LAYOUTS_ERROR_CODE =
  "UNSAFE_CUSTOM_LAYOUTS_DISABLED";

/** Database/user supplied TSX is disabled unless a deployer deliberately opts in. */
export function isUnsafeCustomLayoutServerEnabled(): boolean {
  return process.env.ENABLE_UNSAFE_CUSTOM_LAYOUTS === "true";
}

/** Browser execution requires a separate public build-time opt-in. */
export function isUnsafeCustomLayoutClientEnabled(): boolean {
  return process.env.NEXT_PUBLIC_ENABLE_UNSAFE_CUSTOM_LAYOUTS === "true";
}
