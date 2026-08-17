"use client";

import { useState } from "react";
import { LogOut } from "lucide-react";

import { getApiUrl } from "@/utils/api";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";
import { fetchWithTimeout } from "@/utils/fetchWithTimeout";
import {
  MixpanelEvent,
  trackEvent,
  trackEventImmediately,
} from "@/utils/mixpanel";

type LogoutButtonProps = {
  label?: string;
  pendingLabel?: string;
  className?: string;
  iconOnly?: boolean;
};

export default function LogoutButton({
  label = "Logout",
  pendingLabel = "Signing out...",
  className = "",
  iconOnly = false,
}: LogoutButtonProps) {
  const { locale } = useI18n();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleLogout = async () => {
    if (isSubmitting) {
      return;
    }

    setIsSubmitting(true);
    trackEvent(MixpanelEvent.Auth_SignOut_Started, {
      source: "logout_button",
    });
    try {
      const response = await fetchWithTimeout(getApiUrl("/api/v1/auth/logout"), {
        method: "POST",
        credentials: "include",
      }, 10_000);
      if (response.ok) {
        await trackEventImmediately(MixpanelEvent.Auth_Signed_Out, {
          source: "logout_button",
        });
      } else {
        await trackEventImmediately(MixpanelEvent.Auth_SignOut_Failed, {
          source: "logout_button",
          status_code: response.status,
        });
      }
    } catch (logoutError) {
      await trackEventImmediately(MixpanelEvent.Auth_SignOut_Failed, {
        source: "logout_button",
        status_code: null,
        error_type:
          logoutError instanceof Error ? logoutError.name : "UnknownError",
      });
      // Always route back to auth gate even if backend logout fails.
    } finally {
      window.location.replace(localizePathname("/", locale));
      setIsSubmitting(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={isSubmitting}
      className={className}
      aria-label={label}
      title={label}
    >
      <LogOut className="h-4 w-4" />
      {!iconOnly ? <span>{isSubmitting ? pendingLabel : label}</span> : null}
    </button>
  );
}
