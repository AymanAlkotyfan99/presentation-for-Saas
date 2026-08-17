import { getServerAuthStatus } from "@/utils/serverAuth";
import AccountPage from "./AccountPage";

export default async function AccountRoute() {
  const status = await getServerAuthStatus();
  return <AccountPage username={status.username ?? "Bayanly user"} />;
}

