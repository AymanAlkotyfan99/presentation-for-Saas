'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { setCanChangeKeys, setLLMConfig } from '@/store/slices/userConfig';
import { hasValidLLMConfig, normalizeLLMConfig } from '@/utils/storeHelpers';
import { usePathname, useRouter } from 'next/navigation';
import { useDispatch } from 'react-redux';
import { isOllamaModelAvailable } from '@/utils/providerUtils';
import { LLMConfig } from '@/types/llm_config';
import { getApiUrl } from '@/utils/api';
import { notify } from '@/components/ui/sonner';
import { PRESENTON_SPLASH_MIN_DURATION_MS } from '@/components/ui/presenton-splash-loader';
import { DISPLAY_PRODUCT } from '@/lib/product-metadata';
import {
  localeFromPathname,
  localizePathname,
  stripLocalePrefix,
} from '@/i18n/routing';
import { fetchWithTimeout } from '@/utils/fetchWithTimeout';
import { useI18n } from '@/i18n/catalog';

const NAVIGATION_POLL_INTERVAL_MS = 100;
const NAVIGATION_TIMEOUT_MS = 5000;

function normalizeApplicationPathname(pathname: string) {
  const stripped = stripLocalePrefix(pathname || '/');
  if (stripped === '/') return stripped;
  return stripped.replace(/\/+$/, '') || '/';
}

function hasReachedNavigationTarget(currentPathname: string, targetPathname: string) {
  if (
    normalizeApplicationPathname(currentPathname) !==
    normalizeApplicationPathname(targetPathname)
  ) {
    return false;
  }

  const targetLocale = localeFromPathname(targetPathname);
  return !targetLocale || localeFromPathname(currentPathname) === targetLocale;
}

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

      {/* <div className="absolute left-1/2 top-[calc(50%+123.47px)] flex h-[42px] w-[352px] max-w-[calc(100%-32px)] -translate-x-1/2 items-center gap-1 rounded-md bg-[#F5F8FF] px-[14px]">
        <Image
          alt=""
          aria-hidden="true"
          className="h-[14px] w-[14px] shrink-0"
          height={14}
          src="/figma-assets/configuration-status-icon.svg"
          width={14}
        />
        <p className="whitespace-nowrap font-manrope text-[14px] font-medium leading-normal tracking-[0.3px] text-[#6172F3]">
          Checking &amp; configuring application assets.
        </p>
      </div> */}
    </div>
  );
}

export function ConfigurationInitializer({ children }: { children: React.ReactNode }) {
  const dispatch = useDispatch();
  const { t } = useI18n();

  const route = usePathname() || '/';
  const applicationRoute = normalizeApplicationPathname(route);
  const routeLocale = localeFromPathname(route);
  const shouldShowStartupSplash = !applicationRoute.startsWith('/pdf-maker');
  const isPlatformSettingsRoute =
    applicationRoute === '/admin/platform' || applicationRoute.startsWith('/admin/platform/');
  const [isLoading, setIsLoading] = useState(
    () => shouldShowStartupSplash
  );
  const [hasMetSplashDuration, setHasMetSplashDuration] = useState(
    () => !shouldShowStartupSplash
  );
  const router = useRouter();
  const navigationTimers = useRef<{
    interval: number | null;
    timeout: number | null;
  }>({ interval: null, timeout: null });

  const clearNavigationTimers = useCallback(() => {
    if (navigationTimers.current.interval !== null) {
      window.clearInterval(navigationTimers.current.interval);
      navigationTimers.current.interval = null;
    }
    if (navigationTimers.current.timeout !== null) {
      window.clearTimeout(navigationTimers.current.timeout);
      navigationTimers.current.timeout = null;
    }
  }, []);

  // Fetch user config state
  useEffect(() => {
    fetchUserConfigState();
    // Startup configuration is intentionally fetched once for this mounted app session.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!shouldShowStartupSplash) {
      setHasMetSplashDuration(true);
      return;
    }

    const timeout = window.setTimeout(() => {
      setHasMetSplashDuration(true);
    }, PRESENTON_SPLASH_MIN_DURATION_MS);

    return () => window.clearTimeout(timeout);
  }, [shouldShowStartupSplash]);

  useEffect(() => clearNavigationTimers, [clearNavigationTimers]);

  const setLoadingToFalseAfterNavigatingTo = useCallback((pathname: string) => {
    clearNavigationTimers();

    if (hasReachedNavigationTarget(window.location.pathname, pathname)) {
      setIsLoading(false);
      return;
    }

    navigationTimers.current.interval = window.setInterval(() => {
      if (hasReachedNavigationTarget(window.location.pathname, pathname)) {
        clearNavigationTimers();
        setIsLoading(false);
      }
    }, NAVIGATION_POLL_INTERVAL_MS);

    navigationTimers.current.timeout = window.setTimeout(() => {
      const currentPathname = window.location.pathname;
      clearNavigationTimers();
      console.error(
        `[ConfigurationInitializer] Navigation target was not reached: ${pathname} (current: ${currentPathname})`,
      );
      setIsLoading(false);
    }, NAVIGATION_TIMEOUT_MS);
  }, [clearNavigationTimers]);

  const navigateToApplicationPath = (pathname: string) => {
    const target = routeLocale ? localizePathname(pathname, routeLocale) : pathname;
    router.push(target);
    setLoadingToFalseAfterNavigatingTo(target);
  };

  const finishWithUnavailableGeneration = () => {
    if (applicationRoute === '/') {
      navigateToApplicationPath('/dashboard');
      return;
    }
    if (!isPlatformSettingsRoute) {
      notify.error(
        t('errors.generationUnavailableTitle'),
        t('errors.generationUnavailableDescription'),
        { id: 'generation-platform-unavailable' },
      );
    }
    setIsLoading(false);
  };

  const fetchUserConfigState = async () => {
    if (applicationRoute.startsWith('/pdf-maker')) {
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    let canChangeKeys = false;
    try {
      const res = await fetchWithTimeout('/api/can-change-keys', {}, 10_000);
      if (!res.ok) throw new Error(`can-change-keys returned ${res.status}`);
      const data = await res.json();
      canChangeKeys = data.canChange ?? false;
    } catch (e) {
      console.error('Failed to fetch can-change-keys:', e);
      canChangeKeys = false;
    }
    dispatch(setCanChangeKeys(canChangeKeys));

    if (canChangeKeys) {
      let llmConfig: LLMConfig = {};
      try {
        const res = await fetchWithTimeout('/api/user-config', {}, 10_000);
        if (!res.ok) throw new Error(`user-config returned ${res.status}`);
        llmConfig = await res.json();
      } catch (e) {
        console.error('Failed to fetch user config:', e);
        llmConfig = {};
      }
      if (!llmConfig.LLM) {
        llmConfig.LLM = 'openai';
      }
      llmConfig = normalizeLLMConfig(llmConfig);

      dispatch(setLLMConfig(llmConfig));

      const isValid = hasValidLLMConfig(llmConfig);
      if (applicationRoute.startsWith('/pdf-maker')) {
        setIsLoading(false);
        return;
      }
      if (isValid) {
        // Check if the selected Ollama model is pulled
        if (llmConfig.LLM === 'ollama' && llmConfig.OLLAMA_MODEL) {
          let isAvailable = false;
          try {
            isAvailable = await isOllamaModelAvailable(
              llmConfig.OLLAMA_MODEL,
              llmConfig.OLLAMA_URL
            );
          } catch (error) {
            console.error('Configured text service is unavailable:', error);
          }
          if (!isAvailable) {
            finishWithUnavailableGeneration();
            return;
          }
        }
        if (llmConfig.LLM === 'custom') {
          const isAvailable = await checkIfSelectedCustomModelIsAvailable(llmConfig);
          if (!isAvailable) {
            finishWithUnavailableGeneration();
            return;
          }
        }
        if (llmConfig.LLM === 'deepseek') {
          const isAvailable = await checkIfSelectedDeepSeekModelIsAvailable(llmConfig);
          if (!isAvailable) {
            finishWithUnavailableGeneration();
            return;
          }
        }
        if (applicationRoute === '/') {
          navigateToApplicationPath('/dashboard');
        } else {
          setIsLoading(false);
        }
      } else {
        finishWithUnavailableGeneration();
      }
    } else {
      try {
        const res = await fetchWithTimeout("/api/runtime-config", {
          cache: "no-store",
        }, 10_000);
        if (res.ok) {
          const runtime = await res.json();
          const runtimeConfig = normalizeLLMConfig(
            (runtime.config || {}) as LLMConfig
          );
          dispatch(setLLMConfig(runtimeConfig));
          if (!runtime.configured) {
            finishWithUnavailableGeneration();
            return;
          }
        }
      } catch (error) {
        console.error("Failed to fetch runtime configuration:", error);
      }
      if (applicationRoute === '/') {
        navigateToApplicationPath('/dashboard');
      } else {
        setIsLoading(false);
      }
    }
  }


  const checkIfSelectedCustomModelIsAvailable = async (llmConfig: LLMConfig) => {
    try {
      const response = await fetchWithTimeout(getApiUrl('/api/v1/ppt/openai/models/available'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: llmConfig.CUSTOM_LLM_URL,
          api_key: llmConfig.CUSTOM_LLM_API_KEY,
        }),
      }, 15_000);
      const data = await response.json();
      return data.includes(llmConfig.CUSTOM_MODEL);
    } catch (error) {
      console.error('Error fetching custom models:', error);
      return false;
    }
  }

  const checkIfSelectedDeepSeekModelIsAvailable = async (llmConfig: LLMConfig) => {
    try {
      const response = await fetchWithTimeout(getApiUrl('/api/v1/ppt/openai/models/available'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: llmConfig.DEEPSEEK_BASE_URL || "https://api.deepseek.com/v1",
          api_key: llmConfig.DEEPSEEK_API_KEY,
        }),
      }, 15_000);
      const data = await response.json();
      return data.includes(llmConfig.DEEPSEEK_MODEL);
    } catch (error) {
      console.error('Error fetching DeepSeek models:', error);
      return false;
    }
  }


  if (isLoading || !hasMetSplashDuration) {
    return <ConfigurationLoadingScreen />;
  }

  return children;
}
