'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useDispatch } from 'react-redux';
import { setCanChangeKeys, setLLMConfig } from '@/store/slices/userConfig';
import { normalizeLLMConfig } from '@/utils/storeHelpers';
import type { LLMConfig } from '@/types/llm_config';
import { fetchWithTimeout } from '@/utils/fetchWithTimeout';
import { stripLocalePrefix } from '@/i18n/routing';
import { PRESENTON_SPLASH_MIN_DURATION_MS } from '@/components/ui/presenton-splash-loader';
import { DISPLAY_PRODUCT } from '@/lib/product-metadata';

function ConfigurationLoadingScreen() {
  return (
    <div
      aria-busy="true"
      className="fixed inset-0 z-[2147483000] overflow-hidden bg-white"
      role="status"
    >
      <div className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 flex-col items-center gap-7 whitespace-nowrap">
        <div aria-hidden="true" className="configuration-loader" />
        <p className="font-syne text-[18px] font-normal leading-normal tracking-[-0.54px] text-[#191919]">
          Loading {DISPLAY_PRODUCT.shortName}...
        </p>
      </div>
    </div>
  );
}

/**
 * Hydrates deployment/user configuration for protected application routes.
 * External providers are deliberately not probed here: browsing the product
 * must not depend on generation infrastructure being reachable.
 */
export function ConfigurationInitializer({ children }: { children: React.ReactNode }) {
  const dispatch = useDispatch();
  const pathname = usePathname() || '/';
  const [applicationPath] = useState(() => stripLocalePrefix(pathname));
  const shouldShowStartupSplash = !applicationPath.startsWith('/pdf-maker');
  const [isLoading, setIsLoading] = useState(shouldShowStartupSplash);
  const [hasMetSplashDuration, setHasMetSplashDuration] = useState(!shouldShowStartupSplash);

  useEffect(() => {
    if (!shouldShowStartupSplash) {
      setHasMetSplashDuration(true);
      return;
    }
    const timeout = window.setTimeout(
      () => setHasMetSplashDuration(true),
      PRESENTON_SPLASH_MIN_DURATION_MS,
    );
    return () => window.clearTimeout(timeout);
  }, [shouldShowStartupSplash]);

  useEffect(() => {
    let cancelled = false;

    async function hydrateConfiguration() {
      if (applicationPath.startsWith('/pdf-maker')) {
        if (!cancelled) setIsLoading(false);
        return;
      }

      setIsLoading(true);
      let canChangeKeys = false;
      try {
        const response = await fetchWithTimeout('/api/can-change-keys', {}, 10_000);
        if (!response.ok) throw new Error(`can-change-keys returned ${response.status}`);
        const payload = await response.json();
        canChangeKeys = payload.canChange ?? false;
      } catch (error) {
        console.error('Failed to load configuration permissions:', error);
      }
      if (cancelled) return;
      dispatch(setCanChangeKeys(canChangeKeys));

      try {
        const endpoint = canChangeKeys ? '/api/user-config' : '/api/runtime-config';
        const response = await fetchWithTimeout(endpoint, { cache: 'no-store' }, 10_000);
        if (!response.ok) throw new Error(`${endpoint} returned ${response.status}`);
        const payload = await response.json();
        const rawConfig = canChangeKeys ? payload : payload.config;
        const config = normalizeLLMConfig((rawConfig || {}) as LLMConfig);
        if (!cancelled) dispatch(setLLMConfig(config));
      } catch (error) {
        console.error('Failed to load provider configuration:', error);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    }

    void hydrateConfiguration();
    return () => {
      cancelled = true;
    };
  }, [applicationPath, dispatch]);

  if (isLoading || !hasMetSplashDuration) return <ConfigurationLoadingScreen />;
  return children;
}
