import { requireAdminSession } from "@/utils/serverAuth";
import SettingPage from "../../settings/SettingPage";

export default async function PlatformSettingsPage() {
  await requireAdminSession();
  return <SettingPage />;
}
