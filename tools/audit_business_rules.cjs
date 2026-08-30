#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const sandbox = {
  console,
  window: { addEventListener() {} },
  document: { getElementById() { return null; } },
  localStorage: { getItem() { return null; }, setItem() {} },
  navigator: {},
  location: { protocol: "http:" },
  setTimeout,
  clearTimeout,
};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(root, "data", "manifest.js"), "utf8"), sandbox);
vm.runInContext(fs.readFileSync(path.join(root, "data", "normalized", "manifest.js"), "utf8"), sandbox);
vm.runInContext(fs.readFileSync(path.join(root, "js", "app.js"), "utf8"), sandbox);

function evaluate(source) {
  return vm.runInContext(source, sandbox);
}

const salsa = evaluate(`manifest.ingredients.find((item) => item.name === "Salsa de calabaza")`);
evaluate(`state.orders = 4; state.mode = "unidad"`);
sandbox.testItem = { ...salsa, id: 50, usage: 5.4 };
const salsaResult = evaluate(`calculate(testItem)`);
if (salsaResult.min !== 0.8 || salsaResult.max !== 2.3 || salsaResult.presentation !== "Bote 1.86 L") {
  throw new Error(`Salsa de calabaza inválida: ${JSON.stringify(salsaResult)}`);
}

const stoppedIndex = evaluate(`normalizedManifest.ingredients.findIndex((item) => item.stoppedWeek === 31)`);
if (stoppedIndex < 0) throw new Error("No existe muestra Normalizada con término en semana 31");
sandbox.stoppedItem = evaluate(`({ ...normalizedManifest.ingredients[${stoppedIndex}], sourceIngredientId: ${stoppedIndex}, source: "normalizado" })`);
const divisor = evaluate(`averageDivisor(stoppedItem, [28,29,30,31,32,33,34,35])`);
const notice = evaluate(`recipeNotice(stoppedItem)`);
if (divisor !== 3 || !notice.includes("hasta Sem 30") || !notice.includes("Sem 31")) {
  throw new Error(`Regla Normalizados inválida: divisor=${divisor}, aviso=${notice}`);
}

const currentIndex = evaluate(`normalizedManifest.ingredients.findIndex((item) => item.lastWeek === 35)`);
sandbox.currentItem = evaluate(`({ ...normalizedManifest.ingredients[${currentIndex}], sourceIngredientId: ${currentIndex}, source: "normalizado" })`);
const currentNotice = evaluate(`recipeNotice(currentItem)`);
if (!currentNotice.includes("vigente") || !currentNotice.includes("Sem 35")) {
  throw new Error(`Aviso vigente inválido: ${currentNotice}`);
}

console.log(JSON.stringify({
  status: "ok",
  salsa: salsaResult,
  normalizedStopped: { divisor, notice },
  normalizedCurrent: currentNotice,
}));
