import React from "react";
import { AppShell } from "@/components/product-shell/AppShell";
import { getServerAuthStatus } from "@/utils/serverAuth";

const layout = async ({ children }: { children: React.ReactNode }) => {
    const status = await getServerAuthStatus();
    return (
        <AppShell username={status.username ?? "Bayanly user"} role={status.role}>
            {children}
        </AppShell>
    );
};

export default layout;
