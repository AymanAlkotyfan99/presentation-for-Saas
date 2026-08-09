import { useState } from "react";
import { BarChart3, Palette, Pencil } from "lucide-react";
import type { ChartSlideElement } from "@/components/slide-editor/state/state";
import {
  appendChartColorTarget,
  resolvedChartColorTargets,
  updateChartColorTarget,
} from "@/components/slide-editor/charts/chart-data";
import { ChartColorPaletteCard } from "@/components/slide-editor/charts/ChartColorPalette";
import { ChartDataEditorPopover } from "@/components/slide-editor/charts/ChartEditorContent";
import {
  FloatingToolbar,
  FloatingToolbarPanel,
  type FloatingToolbarBox,
} from "@/components/slide-editor/toolbar/FloatingToolbar";
import { inlineStyles } from "@/components/slide-editor/toolbar/inlineStyles";
import { useTranslations } from "@/i18n/catalog";

const DEFAULT_CHART_TOOLBAR_SIZE = { width: 2.5, height: 2.5 };
const CHART_TYPE_OPTIONS: Array<{
  labelKey: string;
  value: ChartSlideElement["chart_type"];
}> = [
    { value: "bar", labelKey: "editor.barChart" },
    { value: "horizontal_bar", labelKey: "editor.horizontalBar" },
    { value: "stacked_bar", labelKey: "editor.stackedBar" },
    { value: "horizontal_stacked_bar", labelKey: "editor.horizontalStackedBar" },
    { value: "line", labelKey: "editor.lineChart" },
    { value: "area", labelKey: "editor.areaChart" },
    { value: "pie", labelKey: "editor.pieChart" },
    { value: "donut", labelKey: "editor.donutChart" },
    { value: "scatter", labelKey: "editor.scatterChart" },
    { value: "radar", labelKey: "editor.radarChart" },
    { value: "polar_area", labelKey: "editor.polarArea" },
  ];

export function ChartToolbarControls({
  element,
  paletteOpen: controlledPaletteOpen,
  onChange,
  onEdit,
  onPaletteOpenChange,
}: {
  element: ChartSlideElement;
  paletteOpen?: boolean;
  onChange: (element: ChartSlideElement) => void;
  onEdit?: () => void;
  onPaletteOpenChange?: (open: boolean) => void;
}) {
  const t = useTranslations();
  const [uncontrolledPaletteOpen, setUncontrolledPaletteOpen] =
    useState(false);
  const [activeColorIndex, setActiveColorIndex] = useState(0);
  const paletteOpen = controlledPaletteOpen ?? uncontrolledPaletteOpen;
  const setPaletteOpen = (open: boolean) => {
    if (onPaletteOpenChange) {
      onPaletteOpenChange(open);
      return;
    }
    setUncontrolledPaletteOpen(open);
  };
  const colorTargets = resolvedChartColorTargets(element);
  const activeTarget =
    colorTargets.find((target) => target.index === activeColorIndex) ??
    colorTargets[0];

  return (
    <>
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          paddingInlineEnd: 8,
          borderInlineEnd: "1px solid #E6E6EA",
        }}
      >
        <BarChart3 size={16} strokeWidth={2} />
        <select
          aria-label={t("editor.chartType")}
          title={t("editor.chartType")}
          value={element.chart_type}
          onChange={(event) =>
            onChange({
              ...element,
              chart_type: event.target.value as ChartSlideElement["chart_type"],
            })
          }
          style={{
            ...inlineStyles.select,
            minWidth: 80,
            maxWidth: 100,
            border: "none",
            paddingInlineStart: 0,
          }}
        >
          {CHART_TYPE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {t(option.labelKey)}
            </option>
          ))}
        </select>
      </div>

      {onEdit ? (
        <button
          type="button"
          aria-label={t("editor.editChartData")}
          title={t("editor.editChartData")}
          onClick={() => {
            setPaletteOpen(false);
            onEdit();
          }}
          style={inlineStyles.iconButton}
        >
          <Pencil size={16} strokeWidth={2} />
        </button>
      ) : null}

      <div style={{ position: "relative" }}>
        <button
          type="button"
          aria-expanded={paletteOpen}
          aria-label={t("editor.chartColors")}
          title={t("editor.chartColors")}
          onClick={() => setPaletteOpen(!paletteOpen)}
          style={{
            ...inlineStyles.iconButton,
            ...(paletteOpen ? inlineStyles.iconButtonActive : {}),
          }}
        >
          <Palette size={16} strokeWidth={2} />
        </button>
        {paletteOpen && activeTarget ? (
          <FloatingToolbarPanel>
            <ChartColorPaletteCard
              colors={colorTargets.map((target) => target.color)}
              onAddColor={() => {
                const nextIndex = Math.min(11, colorTargets.length);
                setActiveColorIndex(nextIndex);
                onChange(appendChartColorTarget(element));
              }}
              onChange={(color) =>
                onChange(
                  updateChartColorTarget(element, activeTarget.index, color),
                )
              }
              onClose={() => setPaletteOpen(false)}
              onSelectIndex={setActiveColorIndex}
              selectedIndex={activeTarget.index}
            />
          </FloatingToolbarPanel>
        ) : null}
      </div>
    </>
  );
}

export function ChartToolbar({
  anchorBox,
  element,
  index,
  scale,
  onChange,
}: {
  anchorBox?: FloatingToolbarBox | null;
  element: ChartSlideElement;
  index: number;
  scale: number;
  onChange: (index: number, element: ChartSlideElement) => void;
}) {
  const [editorOpen, setEditorOpen] = useState(false);

  return (
    <>
      <FloatingToolbar
        anchorBox={
          anchorBox ?? {
            x: (element.position?.x ?? 0) * scale,
            y: (element.position?.y ?? 0) * scale,
            width:
              (element.size?.width ?? DEFAULT_CHART_TOOLBAR_SIZE.width) * scale,
            height:
              (element.size?.height ?? DEFAULT_CHART_TOOLBAR_SIZE.height) * scale,
          }
        }
        fallbackWidth={220}
        inlineEditIgnore
        style={inlineStyles.toolbar}
      >
        <ChartToolbarControls
          element={element}
          onChange={(element) => onChange(index, element)}
          onEdit={() => setEditorOpen(true)}
        />
      </FloatingToolbar>
      {editorOpen ? (
        <ChartDataEditorPopover
          chart={element}
          chartPath={`chart-${index}`}
          onChange={(chart) => onChange(index, chart)}
          onClose={() => setEditorOpen(false)}
        />
      ) : null}
    </>
  );
}
