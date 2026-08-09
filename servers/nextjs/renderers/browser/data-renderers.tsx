import type { ChartElement, TableElement } from "@/generated/presentation-document";
import { resolveParagraphDirection, textFromParagraphs } from "@/renderers/shared/direction";
import { safeColor } from "@/renderers/shared/style";
import type { BrowserElementRendererProps } from "./types";

export function BrowserTableRenderer({ element, context }: BrowserElementRendererProps<TableElement>) {
  return <table style={{ width: "100%", height: "100%", tableLayout: "fixed", borderCollapse: "collapse", color: "#111827" }}>
    <tbody>
      {element.rows.map((row, rowIndex) => <tr key={rowIndex}>
        {row.cells.map((cell, cellIndex) => {
          const paragraph = cell.paragraphs[0];
          const direction = paragraph ? resolveParagraphDirection(paragraph, context.locale, context.direction) : context.direction;
          return <td key={cellIndex} colSpan={cell.columnSpan} rowSpan={cell.rowSpan} dir={direction} style={{ border: "1px solid #9CA3AF", background: safeColor(cell.background, rowIndex < (element.headerRows ?? 0) ? "#E5E7EB" : "#FFFFFF"), padding: 6, textAlign: direction === "rtl" ? "right" : "left", unicodeBidi: "plaintext", overflow: "hidden" }}>
            {textFromParagraphs(cell.paragraphs)}
          </td>;
        })}
      </tr>)}
    </tbody>
  </table>;
}

export function BrowserChartRenderer({ element }: BrowserElementRendererProps<ChartElement>) {
  const width = element.geometry.width;
  const height = element.geometry.height;
  if (element.chartType === "pie" || element.chartType === "donut" || element.chartType === "polar-area") {
    const values = element.series[0]?.values.map((value) => Math.max(0, value)) ?? [];
    const total = Math.max(1, values.reduce((sum, value) => sum + value, 0));
    let angle = -Math.PI / 2;
    const radius = Math.min(width, height) * 0.42;
    return <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" role="img" aria-label={element.title ?? "Chart"}>
      {values.map((value, index) => {
        const next = angle + value / total * Math.PI * 2;
        const path = arcPath(width / 2, height / 2, radius, angle, next, element.chartType === "donut" ? radius * 0.5 : 0);
        angle = next;
        return <path key={index} d={path} fill={palette(index, element.series[0]?.color)} stroke="#FFFFFF" />;
      })}
    </svg>;
  }
  const values = element.series.flatMap(({ values }) => values);
  const max = Math.max(1, ...values.map((value) => Math.abs(value)));
  const categories = Math.max(1, element.categoryLabels?.length ?? Math.max(...element.series.map(({ values }) => values.length), 1));
  const groupWidth = width / categories;
  const barWidth = Math.max(2, groupWidth / Math.max(1, element.series.length + 1));
  return <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" role="img" aria-label={element.title ?? "Chart"}>
    {element.series.flatMap((series, seriesIndex) => series.values.map((value, index) => {
      const barHeight = Math.abs(value) / max * Math.max(1, height - 32);
      return <rect key={`${series.id}:${index}`} x={index * groupWidth + (seriesIndex + 0.5) * barWidth} y={height - barHeight} width={barWidth} height={barHeight} fill={palette(seriesIndex, series.color)} />;
    }))}
  </svg>;
}

function palette(index: number, color?: string) {
  return safeColor(color, ["#2563EB", "#7C3AED", "#059669", "#D97706", "#DC2626"][index % 5]);
}

function arcPath(cx: number, cy: number, outer: number, start: number, end: number, inner: number) {
  const large = end - start > Math.PI ? 1 : 0;
  const p1 = [cx + outer * Math.cos(start), cy + outer * Math.sin(start)];
  const p2 = [cx + outer * Math.cos(end), cy + outer * Math.sin(end)];
  if (!inner) return `M ${cx} ${cy} L ${p1[0]} ${p1[1]} A ${outer} ${outer} 0 ${large} 1 ${p2[0]} ${p2[1]} Z`;
  const p3 = [cx + inner * Math.cos(end), cy + inner * Math.sin(end)];
  const p4 = [cx + inner * Math.cos(start), cy + inner * Math.sin(start)];
  return `M ${p1[0]} ${p1[1]} A ${outer} ${outer} 0 ${large} 1 ${p2[0]} ${p2[1]} L ${p3[0]} ${p3[1]} A ${inner} ${inner} 0 ${large} 0 ${p4[0]} ${p4[1]} Z`;
}
