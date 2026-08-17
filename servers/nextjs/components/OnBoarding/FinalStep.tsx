"use client";

import { ArrowRight, PartyPopper } from 'lucide-react'
import { usePathname, useRouter } from 'next/navigation'
import React, { useCallback, useEffect, useState } from 'react'
import { trackEvent, MixpanelEvent, setTelemetryEnabled } from "@/utils/mixpanel";
import { Switch } from '../ui/switch';
import confetti from 'canvas-confetti';
import { useI18n } from '@/i18n/catalog';
import { localizePathname } from '@/i18n/routing';

const CONFETTI_COLORS = ['#ff00c5', '#f3ff00', '#9500d0', '#00d2f2', '#00ea9b', '#ff7f36'];

function fireRealisticConfetti() {
    confetti({
        particleCount: 300,
        spread: 360,
        origin: { x: 0.5, y: 0.5 },
        colors: CONFETTI_COLORS,
        startVelocity: 60,
        scalar: 1.8,
        gravity: 0.6,
        ticks: 300,
        decay: 0.93,
        zIndex: 9999,
    });
}

const FinalStep = () => {
    const { locale, t } = useI18n();
    const router = useRouter()
    const pathname = usePathname()
    const [trackingEnabled, setTrackingEnabled] = useState<boolean | null>(null);

    useEffect(() => {
        fireRealisticConfetti();
        trackEvent(MixpanelEvent.Onboarding_Step_Viewed, {
            step_name: "finish",
            step_number: 4,
        });
        trackEvent(MixpanelEvent.Onboarding_Completed);
    }, []);

    useEffect(() => {
        async function fetchStatus() {
            try {
                const response = await fetch('/api/telemetry-status');
                if (!response.ok) throw new Error(`telemetry-status returned ${response.status}`);
                const data = await response.json();
                setTrackingEnabled(data?.telemetryEnabled === true);
            } catch {
                setTrackingEnabled(false);
                setTelemetryEnabled(false);
            }
        }
        fetchStatus();
    }, []);

    const handleTrackingToggle = useCallback(async (enabled: boolean) => {
        setTrackingEnabled(enabled);
        if (!enabled) setTelemetryEnabled(false);
        try {
            const response = await fetch('/api/user-config', {
                method: 'POST',
                body: JSON.stringify({
                    ENABLE_ANONYMOUS_TRACKING: enabled ? 'true' : 'false',
                    DISABLE_ANONYMOUS_TRACKING: enabled ? 'false' : 'true',
                }),
            });
            if (!response.ok) throw new Error(`user-config returned ${response.status}`);
            setTelemetryEnabled(enabled);
        } catch {
            setTrackingEnabled(false);
            setTelemetryEnabled(false);
        }
    }, []);

    const handleGoToDashboard = () => {
        trackEvent(MixpanelEvent.Navigation, { from: pathname, to: "/dashboard" });
        router.push(localizePathname('/dashboard', locale))
    }
    const handleGoToUpload = () => {
        trackEvent(MixpanelEvent.Navigation, { from: pathname, to: "/create" });
        router.push(localizePathname('/create', locale))
    }
    return (
        <div className='fixed inset-0 flex h-full w-full flex-col items-center justify-center'>
            <div className='flex flex-col items-center justify-center'>

                <img src="/final_onboarding.png" alt="" aria-hidden="true" className='h-[98px] w-[118px] object-contain' />
                <h1 className='py-2.5 font-unbounded text-[30px] font-normal text-black'>{t("onboarding.welcomeComplete")}</h1>
                <p className='font-syne text-xl font-normal text-[#000000CC]'>{t("onboarding.ready")}</p>

                {trackingEnabled !== null && (
                    <div className='flex items-center gap-3 mt-8 px-5 py-3.5 rounded-[10px] border border-[#EDEEEF] bg-white'>
                        <div>
                            <p className='font-syne text-sm font-medium text-[#191919]'>{t("onboarding.usageAnalytics")}</p>
                            <p className='mt-0.5 font-syne text-[11px] leading-tight text-[#9CA3AF]'>{t("onboarding.usageAnalyticsDescription")}</p>
                        </div>
                        <Switch
                            checked={trackingEnabled}
                            onCheckedChange={handleTrackingToggle}
                            className='data-[state=checked]:bg-[#7C51F8]'
                        />
                    </div>
                )}

                <button onClick={handleGoToUpload} className='mt-8 rounded-[70px] bg-[#7C51F8] px-[23px] py-[15px] font-syne text-lg font-semibold text-white'>{t("onboarding.firstPresentation")}</button>
                <button onClick={fireRealisticConfetti} className='mt-3 flex items-center gap-1.5 text-sm text-[#7A5AF8] font-syne font-medium hover:underline'>
                    <PartyPopper className='h-4 w-4' /> {t("onboarding.celebrateAgain")}
                </button>
            </div>
            <button onClick={handleGoToDashboard} className='absolute bottom-20 end-10 flex items-center gap-2 font-syne text-xs font-normal uppercase text-[#7A5AF8]'>{t("onboarding.goToDashboard")} <ArrowRight className='h-4 w-4 text-[#7A5AF8] rtl:rotate-180' /></button>
        </div>
    )
}

export default FinalStep
