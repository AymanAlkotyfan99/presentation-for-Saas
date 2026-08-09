"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import Wrapper from "@/components/Wrapper";
import { FileText, Plus, ArrowRight } from "lucide-react";
import { useI18n } from "@/i18n/catalog";
import { localizePathname } from "@/i18n/routing";

const EmptyStateView: React.FC = () => {
    const { locale, t } = useI18n();
    const router = useRouter();

    return (
        <Wrapper className="bg-white">
            <div className="max-w-[800px] h-[calc(100vh-72px)] font-syne flex justify-center items-center mx-auto px-4 sm:px-6 pb-6">
                <div className="text-center space-y-8">
                    {/* Icon */}
                    <div className="flex justify-center">
                        <div className="relative">
                            <div className="w-24 h-24 bg-gradient-to-br from-blue-50 to-indigo-100 rounded-full flex items-center justify-center">
                                <FileText className="w-12 h-12 text-indigo-600" />
                            </div>
                            <div className="absolute -top-2 -right-2 w-8 h-8 bg-red-100 rounded-full flex items-center justify-center">
                                <Plus className="w-4 h-4 text-red-600" />
                            </div>
                        </div>
                    </div>

                    {/* Content */}
                    <div className="space-y-4">
                        <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 font-instrument_sans">
                            {t("outline.missingPresentationTitle")}
                        </h1>
                        <p className="text-lg text-gray-600 max-w-md mx-auto leading-relaxed">
                            {t("outline.missingPresentationDescription")}
                        </p>
                    </div>

                    {/* Action Button */}
                    <div className="pt-4">
                        <Button
                            onClick={() => router.push(localizePathname("/upload", locale))}
                            className="group bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white px-8 py-4 rounded-xl text-lg font-semibold shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105"
                        >
                            <Plus className="me-2 h-5 w-5" />
                            {t("outline.createNewPresentation")}
                            <ArrowRight className="ms-2 h-5 w-5 transition-transform duration-200 group-hover:translate-x-1 rtl:rotate-180" />
                        </Button>
                    </div>

                </div>
            </div>
        </Wrapper>
    );
};

export default EmptyStateView;
