"use client";

import React from "react";
import Link from "next/link";
import { Layout, Plus } from "lucide-react";
import { BRAND_ASSETS, DISPLAY_PRODUCT } from "@/lib/product-metadata";
import { LocaleSwitcher } from "@/components/LocaleSwitcher";
import { useTranslations } from "@/i18n/catalog";

const Header: React.FC = () => {
  const t = useTranslations();
  return (
    <header className="w-full border-b bg-white/60 backdrop-blur supports-[backdrop-filter]:bg-white/60 sticky top-0 z-50">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <img src={BRAND_ASSETS.darkLogo} alt={DISPLAY_PRODUCT.name} className="h-8 w-auto object-contain" />
          </Link>

          <nav className="flex items-center gap-4" aria-label={t("navigation.openMenu")}>
            <Link href="/custom-layout" className="inline-flex items-center gap-2 text-gray-700 hover:text-gray-900">
              <Plus className="w-5 h-5" />
              <span className="text-sm font-medium font-inter">{t("templates.createCustom")}</span>
            </Link>
            <Link href="/template-preview" className="inline-flex items-center gap-2 text-gray-700 hover:text-gray-900">
              <Layout className="w-5 h-5" />
              <span className="text-sm font-medium font-inter">{t("navigation.templates")}</span>
            </Link>
            <LocaleSwitcher compact />
          </nav>
        </div>
      </div>
    </header>
  );
};

export default Header;
