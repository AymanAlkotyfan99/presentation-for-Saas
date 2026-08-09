import React from 'react'
import { useI18n } from '@/i18n/catalog'
import { formatNumber } from '@/lib/locale-format'

interface StepIndicatorProps {
  currentStep: number
}

const steps = [
  { step: 1, label: 'theme.brand' },
  { step: 2, label: 'theme.palette' },
  { step: 3, label: 'theme.fonts' },
  { step: 4, label: 'theme.logo' },
]

export const StepIndicator: React.FC<StepIndicatorProps> = ({ currentStep }) => {
  const { locale, t } = useI18n()
  return (
  <div className="flex min-w-[104px] flex-col items-center gap-7 border-e border-[#EDEEEF] px-4 pt-8">
    {steps.map(({ step, label }) => {
      const isActive = currentStep === step
      return (
        <div key={step} className="flex flex-col items-center gap-1.5 px-3  ">
          <span
            className={`px-2 py-0.5 rounded-full text-[9px] font-medium ${isActive
              ? 'bg-[#7A5AF8] text-white'
              : 'bg-white text-[#404348] border border-[#EDEEEF]'
              }`}
          >
            {t('theme.step', { number: formatNumber(step, locale) })}
          </span>
          <span className="text-[11px] font-normal text-black">{t(label)}</span>
        </div>
      )
    })}
  </div>
  )
}
