import { Arc, Group, Line, Rect, Text } from "react-konva";
import type { ChartElement, TableElement } from "@/generated/presentation-document";
import type { KonvaElementRendererProps } from "./types";
import { resolveParagraphDirection, textFromParagraphs } from "@/renderers/shared/direction";
import { safeColor } from "@/renderers/shared/style";

export function TableRenderer({ element, context }: KonvaElementRendererProps<TableElement>) {
  const rowHeight = element.geometry.height / Math.max(1, element.rows.length);
  const maxColumns = Math.max(1, ...element.rows.map((row) => row.cells.length));
  const columnWidth = element.geometry.width / maxColumns;
  return <Group>
    {element.rows.flatMap((row, rowIndex) => row.cells.map((cell, columnIndex) => {
      const paragraph = cell.paragraphs[0];
      const direction = paragraph ? resolveParagraphDirection(paragraph, context.locale, context.direction) : context.direction;
      return <Group key={`${rowIndex}:${columnIndex}`} x={columnIndex * columnWidth} y={rowIndex * rowHeight}>
        <Rect width={columnWidth} height={rowHeight} fill={safeColor(cell.background, rowIndex < (element.headerRows ?? 0) ? "#E5E7EB" : "#FFFFFF")} stroke="#9CA3AF" strokeWidth={1} />
        <Text width={columnWidth} height={rowHeight} padding={6} text={textFromParagraphs(cell.paragraphs)} direction={direction} align={direction === "rtl" ? "right" : "left"} verticalAlign="middle" fill="#111827" fontSize={Math.max(9, Math.min(18, rowHeight / 3))} />
      </Group>;
    }))}
  </Group>;
}

export function ChartRenderer({ element }: KonvaElementRendererProps<ChartElement>) {
  if (element.chartType === "pie" || element.chartType === "donut" || element.chartType === "polar-area") return <PieChart element={element} />;
  const values = element.series.flatMap(({ values }) => values);
  const max = Math.max(1, ...values.map((value) => Math.abs(value)));
  const categories = Math.max(1, element.categoryLabels?.length ?? Math.max(...element.series.map(({ values }) => values.length), 1));
  const groupWidth = element.geometry.width / categories;
  const barWidth = Math.max(2, groupWidth / Math.max(1, element.series.length + 1));
  return <Group>
    <Line points={[0, element.geometry.height - 20, element.geometry.width, element.geometry.height - 20]} stroke="#6B7280" strokeWidth={1} />
    {element.series.flatMap((series, seriesIndex) => series.values.map((value, valueIndex) => {
      const height = Math.abs(value) / max * Math.max(1, element.geometry.height - 48);
      return <Rect key={`${series.id}:${valueIndex}`} x={valueIndex * groupWidth + (seriesIndex + 0.5) * barWidth} y={element.geometry.height - 20 - height} width={barWidth} height={height} fill={safeColor(series.color, palette(seriesIndex))} />;
    }))}
  </Group>;
}

function PieChart({ element }: { element: ChartElement }) {
  const values = element.series[0]?.values.map((value) => Math.max(0, value)) ?? [];
  const total = Math.max(1, values.reduce((sum, value) => sum + value, 0));
  const radius = Math.min(element.geometry.width, element.geometry.height) * 0.42;
  let angle = 0;
  return <Group x={element.geometry.width / 2} y={element.geometry.height / 2}>
    {values.map((value, index) => {
      const portion = value / total * 360;
      const start = angle;
      angle += portion;
      return <Arc key={index} innerRadius={element.chartType === "donut" ? radius * 0.5 : 0} outerRadius={radius} angle={portion} rotation={start - 90} fill={safeColor(element.series[0]?.color, palette(index))} stroke="#FFFFFF" strokeWidth={1} />;
    })}
  </Group>;
}

function palette(index: number) {
  return ["#2563EB", "#7C3AED", "#059669", "#D97706", "#DC2626"][index % 5];
}
