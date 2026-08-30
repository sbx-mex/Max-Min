#!/usr/bin/env node
"use strict";

const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { jsPDF } = require("../vendor/jspdf.umd.min.js");

const root = path.resolve(__dirname, "..");
const manifestSource = fs.readFileSync(path.join(root, "data/manifest.js"), "utf8");
const manifest = JSON.parse(manifestSource.replace(/^window\.MAXMIN_MANIFEST=/, "").trim().replace(/;$/, ""));
const store = manifest.stores.find((item) => item.code === "38107");
if (!store) throw new Error("No se encontró Pedregal 38107");
const storeData = JSON.parse(fs.readFileSync(path.join(root, store.file), "utf8"));
const weeks = [18, 19, 20, 21, 22, 23, 24, 25];
const map = new Map();
for (const week of weeks) {
  const flat = storeData[String(week)] || [];
  for (let index = 0; index < flat.length; index += 3) {
    const categoryId = flat[index];
    const ingredientId = flat[index + 1];
    const cents = flat[index + 2];
    const item = map.get(ingredientId) || { id: ingredientId, categoryId, cents: 0 };
    item.cents += cents;
    map.set(ingredientId, item);
  }
}
const items = [...map.values()].map((item) => ({
  ...item,
  ...manifest.ingredients[item.id],
  category: manifest.categories[item.categoryId],
  usage: item.cents / 100 / weeks.length,
})).sort((a, b) => a.name.localeCompare(b.name, "es", { numeric: true })).slice(0, 15);

const context = {
  window: { MAXMIN_MANIFEST: manifest, jspdf: { jsPDF }, addEventListener() {} },
  document: { getElementById() { return null; }, querySelectorAll() { return []; }, body: {} },
  localStorage: { getItem() { return null; }, setItem() {} },
  navigator: {}, console, setTimeout, clearTimeout, URL,
  HTMLInputElement: class HTMLInputElement {},
  __items: items,
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(path.join(root, "js/app.js"), "utf8"), context, { filename: "js/app.js" });
vm.runInContext(`
  state.store = manifest.stores.find((item) => item.code === "38107");
  state.weeks = new Set([18,19,20,21,22,23,24,25]);
  state.orders = 2;
  state.mode = "unidad";
  state.overrides = {};
  globalThis.__pdf = buildPdf(globalThis.__items);
`, context);
const output = process.argv[2] ? path.resolve(process.argv[2]) : path.join(root, "docs/Etiquetas_MIN_MAX_Muestra_38107_Sem18-25.pdf");
fs.mkdirSync(path.dirname(output), { recursive: true });
fs.writeFileSync(output, Buffer.from(context.__pdf.output("arraybuffer")));
console.log(JSON.stringify({ output, labels: items.length, pages: context.__pdf.internal.getNumberOfPages() }));
