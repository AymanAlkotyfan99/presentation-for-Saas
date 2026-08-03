import { requireAdminSession } from "@/utils/serverAuth";
import AdminPanel from "./AdminPanel";
import { DISPLAY_PRODUCT } from "@/lib/product-metadata";

export const metadata = {
  title: `Admin | ${DISPLAY_PRODUCT.shortName}`,
};

export default async function AdminPage() {
  await requireAdminSession();
  return <AdminPanel />;
}
