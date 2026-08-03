import type { LLMConfig } from "@/types/llm_config";

export const outlineQuickPrompts = [
  "Expand outline", "Shorten outline", "Reorder sections", "Merge similar slides",
  "Split large sections", "Improve conclusion", "Improve introduction",
];

export const presentationQuickPrompts = [
  "Create an executive summary", "Strengthen the story flow",
  "Add data and citations", "Create speaker notes",
];

export const templateV2QuickPrompts = [
  "Improve this slide's layout", "Rewrite this slide for executives",
  "Add a supporting visual", "Make the deck visually consistent",
  "Add data and source citations", "Create speaker notes for this slide",
];

export const editorQuickPrompts = [
  "Rewrite for executives", "Improve slide layout", "Add data & citations",
  "Create speaker notes", "Make the deck consistent",
];

export const outlineEditorQuickPrompts = [
  "Strengthen the story flow", "Make the outline concise", "Reorder the sections",
  "Merge similar slides", "Improve the conclusion",
];

export const quickPromptGroups = [
  { label: "Popular", prompts: ["Make it shorter", "Make this smaller", "Generate a new image and replace this one"] },
  { label: "Add Data", prompts: ["Add data and citations", "Add a chart", "Add a table"] },
  { label: "Add Visuals", prompts: ["Generate a new image and replace this one", "Add a chart", "Add a table"] },
];

export const outlineQuickPromptGroups = [
  { label: "Popular", prompts: ["Make the outline shorter", "Expand the outline", "Strengthen the story flow"] },
  { label: "Structure", prompts: ["Reorder the sections", "Merge similar slides", "Split large sections"] },
  { label: "Refine Content", prompts: ["Rewrite for executives", "Improve the introduction", "Improve the conclusion"] },
];

export function getSelectedTextModel(config: LLMConfig) {
  switch (config.LLM) {
    case "openai": return config.OPENAI_MODEL;
    case "deepseek": return config.DEEPSEEK_MODEL;
    case "google": return config.GOOGLE_MODEL;
    case "vertex": return config.VERTEX_MODEL;
    case "azure": return config.AZURE_OPENAI_MODEL;
    case "bedrock": return config.BEDROCK_MODEL;
    case "openrouter": return config.OPENROUTER_MODEL;
    case "fireworks": return config.FIREWORKS_MODEL;
    case "together": return config.TOGETHER_MODEL;
    case "cerebras": return config.CEREBRAS_MODEL;
    case "litellm": return config.LITELLM_MODEL;
    case "lmstudio": return config.LMSTUDIO_MODEL;
    case "anthropic": return config.ANTHROPIC_MODEL;
    case "ollama": return config.OLLAMA_MODEL;
    case "custom": return config.CUSTOM_MODEL;
    case "codex": return config.CODEX_MODEL;
    default: return undefined;
  }
}
