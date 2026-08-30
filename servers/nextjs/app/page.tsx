import AuthGate from "@/components/Auth/AuthGate";
import { isAuthDisabled } from "@/utils/auth";
import { getServerAuthStatus } from "@/utils/serverAuth";
import { requestLocale } from "@/i18n/server";
import { localizePathname } from "@/i18n/routing";
import { redirect } from "next/navigation";

const page = async () => {
    if (isAuthDisabled()) {
        redirect(localizePathname("/dashboard", await requestLocale()));
    }

    const status = await getServerAuthStatus();
    if (status.configured && status.authenticated) {
        redirect(localizePathname("/dashboard", await requestLocale()));
    }

    return <AuthGate />;
};

export default page;
