import { readFile, readdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const messagesDirectory = path.join(repositoryRoot, "servers", "nextjs", "messages");
const sourceRoot = path.join(repositoryRoot, "servers", "nextjs");

export function flattenCatalog(value, prefix = "", output = new Map()) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Catalog namespace ${prefix || "<root>"} must be an object`);
  }
  for (const [key, child] of Object.entries(value)) {
    if (!/^[A-Za-z][A-Za-z0-9]*$/.test(key)) {
      throw new Error(`Invalid catalog key segment: ${prefix ? `${prefix}.` : ""}${key}`);
    }
    const fullKey = prefix ? `${prefix}.${key}` : key;
    if (typeof child === "string") {
      output.set(fullKey, child);
    } else {
      flattenCatalog(child, fullKey, output);
    }
  }
  return output;
}

function variables(message) {
  return [...message.matchAll(/\{([A-Za-z][A-Za-z0-9]*)\}/g)].map((match) => match[1]).sort();
}

function duplicateLineKeys(text, file) {
  const scopes = [];
  const seenByIndent = new Map();
  for (const [index, line] of text.split(/\r?\n/).entries()) {
    const match = line.match(/^(\s*)"([^"]+)"\s*:\s*(.*)$/);
    if (!match) continue;
    const indent = match[1].length;
    for (const key of [...seenByIndent.keys()]) if (key > indent) seenByIndent.delete(key);
    const seen = seenByIndent.get(indent) ?? new Set();
    if (seen.has(match[2])) throw new Error(`${file}:${index + 1}: duplicate key ${match[2]}`);
    seen.add(match[2]);
    seenByIndent.set(indent, seen);
    if (match[3].trim() === "{") scopes.push(match[2]);
  }
}

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const output = [];
  for (const entry of entries) {
    if (["node_modules", ".next", ".next-build", "generated"].includes(entry.name)) continue;
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) output.push(...(await sourceFiles(absolute)));
    else if (/\.(?:ts|tsx)$/.test(entry.name)) output.push(absolute);
  }
  return output;
}

export async function checkLocalization() {
  const catalogEntries = await Promise.all(
    ["en", "ar"].map(async (locale) => {
      const file = path.join(messagesDirectory, `${locale}.json`);
      const text = await readFile(file, "utf8");
      duplicateLineKeys(text, file);
      const parsed = JSON.parse(text);
      return [locale, flattenCatalog(parsed)];
    }),
  );
  const catalogs = Object.fromEntries(catalogEntries);
  const englishKeys = [...catalogs.en.keys()].sort();
  const arabicKeys = [...catalogs.ar.keys()].sort();
  const missingArabic = englishKeys.filter((key) => !catalogs.ar.has(key));
  const missingEnglish = arabicKeys.filter((key) => !catalogs.en.has(key));
  if (missingArabic.length || missingEnglish.length) {
    throw new Error(`Catalog mismatch. Missing ar: ${missingArabic.join(", ") || "none"}; missing en: ${missingEnglish.join(", ") || "none"}`);
  }

  for (const key of englishKeys) {
    const en = catalogs.en.get(key);
    const ar = catalogs.ar.get(key);
    if (!en?.trim() || !ar?.trim()) throw new Error(`Empty translation: ${key}`);
    if (variables(en).join(",") !== variables(ar).join(",")) {
      throw new Error(`Interpolation variables differ for ${key}`);
    }
    for (const [locale, message] of [["en", en], ["ar", ar]]) {
      if (/<\/?[A-Za-z][^>]*>|javascript:|data:text\/html/i.test(message)) {
        throw new Error(`${locale}.${key}: catalogs must contain plain text only`);
      }
    }
  }

  const source = (await Promise.all((await sourceFiles(sourceRoot)).map((file) => readFile(file, "utf8")))).join("\n");
  const unused = englishKeys.filter((key) => !source.includes(`"${key}"`) && !source.includes(`'${key}'`));
  return { keyCount: englishKeys.length, missing: 0, unused };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const report = await checkLocalization();
  console.log(`Localization catalogs valid: ${report.keyCount} English keys, ${report.keyCount} Arabic keys, 0 missing, ${report.unused.length} currently unused.`);
}

