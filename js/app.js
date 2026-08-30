"use strict";

const FACTOR_PEDIDOS = { 2: 5, 3: 4, 4: 3, 5: 2 };
const STORAGE_KEY = "maxmin-remaster-v4";
const PAGE_SIZE = 12;
const LIST_PAGE_SIZE = 20;
const ACOMODO_MAX_ITEMS = 25;
const ACOMODO_PAGE_SIZE = 8;
const NORMALIZED_INGREDIENT_BASE = 1000000;
const NORMALIZED_CATEGORY_BASE = 10000;
const $ = (id) => document.getElementById(id);
const manifest = window.MAXMIN_MANIFEST;
const normalizedManifest = window.MAXMIN_NORMALIZED || { weeks: [], categories: [], ingredients: [], stores: [] };

const state = {
  tab: "etiquetas",
  store: null,
  storeData: null,
  normalizedStoreData: null,
  weeks: new Set(),
  categories: new Set(),
  ingredients: new Set(),
  selected: new Set(),
  overrides: {},
  markerPositions: {},
  orders: 2,
  mode: "unidad",
  catalogSearch: "",
  previewPage: 0,
  aggregated: [],
  filtered: [],
};

let weeksFilter;
let categoriesFilter;
let ingredientsFilter;
let storeFilter;
let toastTimer;
let rackPhotoUrl;
let pendingExportKind = "labels";
let activeMarkerId = null;

function init() {
  if (!manifest || !Array.isArray(manifest.stores) || !manifest.stores.length) {
    document.body.innerHTML = "<main class='app-shell'><section class='card empty-state'>No se pudo cargar el manifiesto de datos. Ejecuta la auditoría del proyecto.</section></main>";
    return;
  }
  restoreState();
  $("versionRange").textContent = `Remaster · Semanas ${manifest.weeks.at(0)}-${manifest.weeks.at(-1)}`;
  buildStoreFilter();
  buildFilters();
  bindEvents();
  setTab(state.tab);
  const preferred = manifest.stores.find((item) => item.code === state.store?.code)
    || manifest.stores.find((item) => item.code === "38107")
    || manifest.stores[0];
  selectStore(preferred, false);
  updateHealth();
  if ("serviceWorker" in navigator && location.protocol.startsWith("http")) {
    window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js").catch(() => {}));
  }
}

function restoreState() {
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); } catch (_) {}
  const weeks = Array.isArray(saved.weeks) && saved.weeks.length ? saved.weeks : latestWeeks(8);
  state.weeks = new Set(weeks.map(Number).filter((week) => manifest.weeks.includes(week)));
  if (!state.weeks.size) state.weeks.add(manifest.weeks.at(-1));
  state.orders = [2, 3, 4, 5].includes(Number(saved.orders)) ? Number(saved.orders) : 2;
  state.mode = saved.mode === "pickpack" ? "pickpack" : "unidad";
  state.overrides = saved.overrides && typeof saved.overrides === "object" ? saved.overrides : {};
  state.markerPositions = saved.markerPositions && typeof saved.markerPositions === "object" ? saved.markerPositions : {};
  state.tab = ["etiquetas", "consulta", "acomodo"].includes(saved.tab) ? saved.tab : "etiquetas";
  if (saved.storeCode) state.store = { code: String(saved.storeCode) };
}

function persistState() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify({
    storeCode: state.store?.code,
    weeks: [...state.weeks],
    orders: state.orders,
    mode: state.mode,
    overrides: state.overrides,
    markerPositions: state.markerPositions,
    tab: state.tab,
  }));
}

function buildStoreFilter() {
  storeFilter = createSingleStoreFilter($("storeFilter"));
}

function buildFilters() {
  weeksFilter = createMultiFilter($("weeksFilter"), {
    label: "Semanas",
    searchable: false,
    options: manifest.weeks.map((week) => ({ value: week, label: `Semana ${week}` })),
    selected: state.weeks,
    onChange: () => { aggregateData(); persistState(); },
  });
  categoriesFilter = createMultiFilter($("categoriesFilter"), {
    label: "Categoría",
    searchable: true,
    options: [],
    selected: state.categories,
    onChange: () => { applyFilters(); },
  });
  ingredientsFilter = createMultiFilter($("ingredientsFilter"), {
    label: "Ingrediente",
    searchable: true,
    options: [],
    selected: state.ingredients,
    onChange: () => { applyFilters(); },
  });
}

function createSingleStoreFilter(root) {
  root.innerHTML = '<label>Tienda / CeCo</label><button class="filter-trigger" type="button" aria-expanded="false"><span>Seleccionar tienda</span><b>⌄</b></button><div class="filter-menu hidden"><input class="filter-search" type="search" autocomplete="off" placeholder="Buscar CeCo o tienda" aria-label="Buscar CeCo o tienda" /><div class="store-options" role="listbox"></div></div>';
  const trigger = root.querySelector(".filter-trigger");
  const menu = root.querySelector(".filter-menu");
  const search = root.querySelector(".filter-search");
  const optionsRoot = root.querySelector(".store-options");
  const orderedStores = [...manifest.stores].sort((a, b) => {
    const statusOrder = Number(a.status === "Cierre Temporal") - Number(b.status === "Cierre Temporal");
    return statusOrder || Number(a.code) - Number(b.code);
  });

  function render() {
    const query = normalize(search.value);
    const matches = orderedStores.filter((store) => !query || normalize(`${store.code} ${store.name} ${store.status || "Abierta"}`).includes(query));
    const visible = matches.slice(0, 100);
    optionsRoot.innerHTML = visible.map((store) => `<button class="store-option ${state.store?.code === store.code ? "selected" : ""} ${store.status === "Cierre Temporal" ? "temporary" : ""}" type="button" role="option" aria-selected="${state.store?.code === store.code}" data-code="${esc(store.code)}"><b>${esc(store.code)}</b><span>${esc(store.name)}</span>${store.status === "Cierre Temporal" ? '<i class="store-status">Temporal</i>' : ""}</button>`).join("") || '<div class="empty-state">Sin coincidencias</div>';
    if (matches.length > visible.length) optionsRoot.insertAdjacentHTML("beforeend", `<div class="filter-hint">Escribe más para acotar ${matches.length} tiendas.</div>`);
  }

  function close() {
    menu.classList.add("hidden");
    trigger.setAttribute("aria-expanded", "false");
  }

  trigger.addEventListener("click", () => {
    document.querySelectorAll(".filter-menu").forEach((item) => { if (item !== menu) item.classList.add("hidden"); });
    menu.classList.toggle("hidden");
    trigger.setAttribute("aria-expanded", String(!menu.classList.contains("hidden")));
    if (!menu.classList.contains("hidden")) { search.value = ""; render(); search.focus(); }
  });
  search.addEventListener("input", render);
  optionsRoot.addEventListener("click", (event) => {
    const button = event.target.closest(".store-option");
    if (!button) return;
    const store = manifest.stores.find((item) => item.code === button.dataset.code);
    if (!store) return;
    close();
    selectStore(store, true);
  });
  document.addEventListener("click", (event) => { if (!root.contains(event.target)) close(); });
  return {
    setValue(store) {
      trigger.querySelector("span").textContent = store ? store.label : "Seleccionar tienda";
      render();
    },
  };
}

function createMultiFilter(root, config) {
  root.innerHTML = `<label>${esc(config.label)}</label><button class="filter-trigger" type="button" aria-expanded="false"><span>Todos</span><b>⌄</b></button><div class="filter-menu hidden">${config.searchable ? '<input class="filter-search" type="search" placeholder="Buscar..." />' : ""}<div class="filter-menu-actions"><button class="link-button select-all" type="button">Seleccionar todo</button><button class="link-button clear-all" type="button">Limpiar</button></div><div class="filter-options"></div></div>`;
  const trigger = root.querySelector(".filter-trigger");
  const menu = root.querySelector(".filter-menu");
  const search = root.querySelector(".filter-search");
  let options = config.options;

  function summary() {
    const chosen = options.filter((option) => config.selected.has(option.value));
    trigger.querySelector("span").textContent = chosen.length === 0 || chosen.length === options.length
      ? "Todos"
      : chosen.length === 1 ? chosen[0].label : `${chosen.length} seleccionados`;
  }

  function render() {
    const query = normalize(search?.value || "");
    const visible = options.filter((option) => !query || normalize(option.label).includes(query));
    root.querySelector(".filter-options").innerHTML = visible.map((option) => `<label class="filter-option"><input type="checkbox" value="${esc(String(option.value))}" ${config.selected.has(option.value) ? "checked" : ""} /><span>${esc(option.label)}</span></label>`).join("") || '<div class="empty-state">Sin opciones</div>';
    summary();
  }

  function commit() {
    summary();
    config.onChange();
  }

  trigger.addEventListener("click", () => {
    document.querySelectorAll(".filter-menu").forEach((item) => { if (item !== menu) item.classList.add("hidden"); });
    menu.classList.toggle("hidden");
    trigger.setAttribute("aria-expanded", String(!menu.classList.contains("hidden")));
    if (!menu.classList.contains("hidden")) { render(); search?.focus(); }
  });
  search?.addEventListener("input", render);
  root.querySelector(".filter-options").addEventListener("change", (event) => {
    if (!(event.target instanceof HTMLInputElement)) return;
    const option = options.find((item) => String(item.value) === event.target.value);
    if (!option) return;
    if (event.target.checked) config.selected.add(option.value); else config.selected.delete(option.value);
    if (config.label === "Semanas" && !config.selected.size) config.selected.add(option.value);
    render(); commit();
  });
  root.querySelector(".select-all").addEventListener("click", () => { options.forEach((option) => config.selected.add(option.value)); render(); commit(); });
  root.querySelector(".clear-all").addEventListener("click", () => {
    config.selected.clear();
    if (config.label === "Semanas" && options.length) config.selected.add(options.at(-1).value);
    render(); commit();
  });
  document.addEventListener("click", (event) => {
    if (!root.contains(event.target)) { menu.classList.add("hidden"); trigger.setAttribute("aria-expanded", "false"); }
  });
  render();
  return {
    setOptions(nextOptions) {
      options = nextOptions;
      for (const value of [...config.selected]) if (!options.some((option) => option.value === value)) config.selected.delete(value);
      render();
    },
    render,
  };
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((button) => button.addEventListener("click", () => setTab(button.dataset.tab)));
  $("ordersSelect").value = String(state.orders);
  $("modeSelect").value = state.mode;
  $("ordersSelect").addEventListener("change", () => { state.orders = Number($("ordersSelect").value); persistState(); renderAll(); });
  $("modeSelect").addEventListener("change", () => { state.mode = $("modeSelect").value; persistState(); renderAll(); });
  $("catalogSearch").addEventListener("input", () => { state.catalogSearch = $("catalogSearch").value; applyFilters(); });
  $("selectFilteredButton").addEventListener("click", selectFiltered);
  $("addVisibleButton").addEventListener("click", selectFiltered);
  $("clearSelectionButton").addEventListener("click", clearSelection);
  $("clearFiltersButton").addEventListener("click", resetFilters);
  document.querySelectorAll("[data-week-preset]").forEach((button) => button.addEventListener("click", () => setWeekPreset(button.dataset.weekPreset)));
  $("resetButton").addEventListener("click", resetCurrent);
  $("exportLabelsButton").addEventListener("click", () => openExportConfirmation("labels"));
  $("exportListButton").addEventListener("click", () => openExportConfirmation("list"));
  $("exportSelectedLabelsButton").addEventListener("click", () => openExportConfirmation("labels"));
  $("addAcomodoItemsButton").addEventListener("click", addAcomodoItems);
  $("clearAcomodoItemsButton").addEventListener("click", clearAcomodoItems);
  $("exportAcomodoButton").addEventListener("click", () => openExportConfirmation("acomodo"));
  $("previousPreview").addEventListener("click", () => { state.previewPage = Math.max(0, state.previewPage - 1); renderPreview(); });
  $("nextPreview").addEventListener("click", () => { state.previewPage += 1; renderPreview(); });
  $("catalogList").addEventListener("change", onCatalogChange);
  $("consultaBody").addEventListener("change", onConsultaChange);
  $("photoInput").addEventListener("change", onPhotoChange);
  $("photoCameraInput").addEventListener("change", onPhotoChange);
  $("enhancePhotoButton").addEventListener("click", togglePhotoEnhancement);
  $("clearPhotoButton").addEventListener("click", clearPhoto);
  $("markerList").addEventListener("dragstart", onMarkerListDragStart);
  $("markerList").addEventListener("click", onMarkerListClick);
  $("photoStage").addEventListener("dragover", onPhotoStageDragOver);
  $("photoStage").addEventListener("dragleave", () => $("photoStage").classList.remove("drop-ready"));
  $("photoStage").addEventListener("drop", onPhotoStageDrop);
  $("photoStage").addEventListener("click", onPhotoStageClick);
  $("cancelExportButton").addEventListener("click", () => $("confirmExportDialog").close());
  $("confirmExportButton").addEventListener("click", () => { $("confirmExportDialog").close(); runConfirmedExport(); });
  $("closeExportDialog").addEventListener("click", () => $("exportDialog").close());
  document.querySelectorAll(".internal-pdf-link").forEach((link) => link.addEventListener("click", openSupportPdf));
  $("closeSupportPdfButton").addEventListener("click", () => { $("supportPdfDialog").close(); $("supportPdfFrame").src = "about:blank"; });
  $("supportPdfDialog").addEventListener("close", () => { $("supportPdfFrame").src = "about:blank"; });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.querySelectorAll(".filter-menu").forEach((menu) => menu.classList.add("hidden"));
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("catalogSearch").focus(); }
  });
}

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${tab}`));
  updateGuide(tab);
  persistState();
  renderAll();
}

function updateGuide(tab) {
  const guides = {
    etiquetas: ["Ruta rápida · Etiquetas", ["Filtra tienda y semanas", "Elige ingredientes", "Revisa las fichas", "Confirma y exporta"]],
    consulta: ["Ruta rápida · Consulta", ["Filtra el alcance", "Revisa la tabla", "Elige una salida", "Confirma el PDF"]],
    acomodo: ["Ruta rápida · Acomodo", ["Filtra el rack", "Toma la foto", "Elige y ubica artículos", "Revisa y exporta"]],
  };
  const [title, steps] = guides[tab] || guides.etiquetas;
  $("guideTitle").textContent = title;
  $("guideSteps").innerHTML = steps.map((step, index) => `<span class="workflow-step" data-step="${index + 1}"><b>${index + 1}</b><em>${esc(step)}</em></span>`).join("");
  updateWorkflowProgress();
}

function updateWorkflowProgress() {
  const steps = [...document.querySelectorAll("#guideSteps .workflow-step")];
  if (!steps.length) return;
  const selected = selectedItemsCurrent().length;
  const visible = positiveReportItems().length;
  const hasPhoto = $("photoStage").classList.contains("has-photo");
  const placed = Object.keys(state.markerPositions[state.store?.code] || {}).length;
  let current = 1;
  if (state.storeData && state.weeks.size) current = 2;
  if (state.tab === "etiquetas" && selected) current = 4;
  if (state.tab === "consulta" && visible) current = 3;
  if (state.tab === "acomodo") current = !hasPhoto ? 2 : placed ? 4 : 3;
  steps.forEach((step, index) => {
    const number = index + 1;
    step.classList.toggle("done", number < current);
    step.classList.toggle("current", number === current);
  });
}

async function selectStore(store, notify) {
  if (state.store?.code === store.code && state.storeData) { storeFilter.setValue(store); return; }
  showLoading("Cargando tienda", `${store.code} · ${store.name}`);
  try {
    const normalizedStore = normalizedManifest.stores.find((item) => item.code === store.code);
    [state.storeData, state.normalizedStoreData] = await Promise.all([
      fetchStoreData(store.file, manifest.generated),
      normalizedStore ? fetchStoreData(normalizedStore.file, normalizedManifest.generated) : Promise.resolve({}),
    ]);
    state.store = store;
    state.categories.clear();
    state.ingredients.clear();
    state.selected.clear();
    state.previewPage = 0;
    storeFilter.setValue(store);
    aggregateData();
    persistState();
    if (notify) toast(`Tienda cargada: ${store.label}`);
  } catch (error) {
    console.error(error);
    toast("No se pudo cargar la tienda. Revisa la conexión e inténtalo nuevamente.");
  } finally { hideLoading(); }
}

function aggregateData() {
  if (!state.storeData) return;
  const selectedWeeks = [...state.weeks].sort((a, b) => a - b);
  const map = new Map();
  function collect(sourceData, ingredientBase, categoryBase, source) {
    for (const week of selectedWeeks) {
      const flat = sourceData?.[String(week)] || [];
      for (let index = 0; index < flat.length; index += 3) {
        const sourceCategoryId = flat[index];
        const sourceIngredientId = flat[index + 1];
        const cents = flat[index + 2];
        const id = ingredientBase + sourceIngredientId;
        let item = map.get(id);
        if (!item) {
          item = {
            id,
            categoryId: categoryBase + sourceCategoryId,
            sourceIngredientId,
            sourceCategoryId,
            source,
            cents: 0,
            weeksWithUsage: 0,
          };
          map.set(id, item);
        }
        item.cents += cents;
        item.weeksWithUsage += cents > 0 ? 1 : 0;
      }
    }
  }
  collect(state.storeData, 0, 0, "principal");
  collect(state.normalizedStoreData, NORMALIZED_INGREDIENT_BASE, NORMALIZED_CATEGORY_BASE, "normalizado");
  state.aggregated = [...map.values()].map((item) => ({
    ...item,
    ...(item.source === "normalizado" ? normalizedManifest.ingredients[item.sourceIngredientId] : manifest.ingredients[item.sourceIngredientId]),
    category: item.source === "normalizado" ? normalizedManifest.categories[item.sourceCategoryId] : manifest.categories[item.sourceCategoryId],
    usage: item.cents / 100 / averageDivisor(item, selectedWeeks),
  })).sort((a, b) => a.name.localeCompare(b.name, "es", { numeric: true }));
  const categoryOptions = [...new Map(state.aggregated.map((item) => [item.categoryId, item.category])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1], "es"))
    .map(([value, label]) => ({ value, label }));
  categoriesFilter.setOptions(categoryOptions);
  updateIngredientOptions();
  applyFilters();
}

function averageDivisor(item, selectedWeeks) {
  if (item.source !== "normalizado") return selectedWeeks.length || 1;
  const reportWeeks = new Set(normalizedManifest.ingredients[item.sourceIngredientId]?.reportWeeks || []);
  return Math.max(1, selectedWeeks.filter((week) => reportWeeks.has(week)).length);
}

function recipeNotice(item) {
  if (item.source !== "normalizado") return "";
  if (item.stoppedWeek) return `Descuento por receta hasta Sem ${item.lastWeek} · dejó de reportarse en Sem ${item.stoppedWeek}`;
  return `Descuento por receta vigente · reporta en Sem ${item.lastWeek}`;
}

function updateIngredientOptions() {
  const base = state.categories.size ? state.aggregated.filter((item) => state.categories.has(item.categoryId)) : state.aggregated;
  ingredientsFilter.setOptions(base.map((item) => ({ value: item.id, label: item.name })));
}

function applyFilters() {
  updateIngredientOptions();
  const query = normalize(state.catalogSearch);
  state.filtered = state.aggregated.filter((item) => {
    if (state.categories.size && !state.categories.has(item.categoryId)) return false;
    if (state.ingredients.size && !state.ingredients.has(item.id)) return false;
    if (query && ![item.name, item.sap, item.code, item.woe].some((value) => normalize(value).includes(query))) return false;
    return true;
  });
  state.previewPage = Math.min(state.previewPage, Math.max(0, Math.ceil(state.selected.size / PAGE_SIZE) - 1));
  renderAll();
}

function calculate(item) {
  const override = state.overrides[item.id];
  const mode = override === "unidad" || override === "pickpack" ? override : state.mode;
  const factor = Math.max(1, Number(item.factor || 1));
  const daily = Number(item.usage || 0) / 7;
  let min = daily;
  let max = daily * (FACTOR_PEDIDOS[state.orders] || 5);
  if (mode === "pickpack") { min = Math.ceil(min / factor); max = Math.ceil(max / factor); }
  else { min = round1(min); max = round1(max); }
  return { mode, min, max, daily, presentation: cleanPresentation(mode === "pickpack" ? item.pickpack : item.unit) };
}

function renderAll() {
  if (!state.store) return;
  updateContext();
  renderCatalog();
  renderPreview();
  renderConsulta();
  renderMarkers();
  updateWorkflowProgress();
}

function updateContext() {
  const weeks = compactWeeks([...state.weeks]);
  $("contextLine").textContent = `${state.store.label} · Uso Sem ${weeks}`;
  $("previewStore").textContent = state.store.label;
  $("previewWeeks").textContent = weeks;
  $("previewDate").textContent = formatDate(manifest.generated);
  const filters = [`Sem ${weeks}`, state.categories.size ? `${state.categories.size} categoría(s)` : "Todas las categorías", state.ingredients.size ? `${state.ingredients.size} ingrediente(s)` : "Todos los ingredientes"];
  $("activeFilterSummary").textContent = filters.join(" · ");
}

function renderCatalog() {
  const positiveItems = positiveReportItems();
  $("filteredCount").textContent = String(positiveItems.length);
  const items = positiveItems.slice(0, 300);
  $("catalogList").innerHTML = items.map((item) => `<label class="catalog-item ${state.selected.has(item.id) ? "selected" : ""}"><input type="checkbox" value="${item.id}" ${state.selected.has(item.id) ? "checked" : ""} /><span class="catalog-copy"><b>${esc(item.name)}</b><small>${esc(item.sap)}${item.code ? ` · DIA ${esc(item.code)}` : ""}</small>${recipeNotice(item) ? `<em class="recipe-note">${esc(recipeNotice(item))}</em>` : ""}</span><span class="usage-badge">${formatNumber(item.usage, 1)}</span></label>`).join("") || '<div class="empty-state">No hay ingredientes con uso mayor a cero para estos filtros.</div>';
  if (positiveItems.length > 300) $("catalogList").insertAdjacentHTML("beforeend", `<div class="empty-state">Mostrando 300 de ${positiveItems.length}. Usa la búsqueda para acotar.</div>`);
}

function renderPreview() {
  const selected = selectedItemsCurrent();
  const pages = Math.max(1, Math.ceil(selected.length / PAGE_SIZE));
  state.previewPage = Math.max(0, Math.min(state.previewPage, pages - 1));
  const pageItems = selected.slice(state.previewPage * PAGE_SIZE, (state.previewPage + 1) * PAGE_SIZE);
  const cards = pageItems.map((item) => labelCardHtml(item));
  while (cards.length < PAGE_SIZE) cards.push('<div class="label-empty">Espacio disponible</div>');
  $("labelPreview").innerHTML = cards.join("");
  $("selectedCount").textContent = String(selected.length);
  $("previewPage").textContent = `Página ${state.previewPage + 1} de ${pages}`;
  $("previousPreview").disabled = state.previewPage === 0;
  $("nextPreview").disabled = state.previewPage >= pages - 1;
  $("exportLabelsButton").disabled = selected.length === 0;
  $("labelsExportHint").textContent = selected.length
    ? `${selected.length} etiqueta(s) · ${Math.ceil(selected.length / PAGE_SIZE)} hoja(s) Carta.`
    : "Elige ingredientes para habilitar el PDF.";
}

function labelCardHtml(item) {
  const calc = calculate(item);
  const dia = item.code || "—";
  const sapNumber = item.woe || "—";
  return `<article class="label-card"><div class="label-name"><b title="${esc(item.sap)}">${esc(item.sap)}</b><small><span title="Nombre Inventario">${esc(item.name)}</span><span>#DIA ${esc(dia)}</span><span>#SAP ${esc(sapNumber)}</span></small></div><div class="label-values"><span class="label-value"><small>MIN</small><b>${formatMinMax(calc.min, calc.mode)}</b></span><span class="label-value"><small>MAX</small><b>${formatMinMax(calc.max, calc.mode)}</b></span></div><div class="label-meta"><span class="format-chip">${calc.mode === "pickpack" ? "PICK PACK" : "UNIDAD"}</span><span>${esc(calc.presentation)}</span><span>${state.orders} PEDIDOS</span></div></article>`;
}

function renderConsulta() {
  const items = positiveReportItems();
  const visibleIds = new Set(items.map((item) => item.id));
  const selectedVisible = selectedItemsCurrent().filter((item) => visibleIds.has(item.id));
  $("consultaVisibleCount").textContent = String(items.length);
  $("consultaSelectedCount").textContent = String(selectedVisible.length);
  $("exportListButton").disabled = items.length === 0;
  $("exportSelectedLabelsButton").disabled = selectedVisible.length === 0;
  $("addVisibleButton").disabled = items.length === 0;
  $("consultaBody").innerHTML = items.map((item) => {
    const calc = calculate(item);
    return `<tr><td><input class="row-select" type="checkbox" data-id="${item.id}" ${state.selected.has(item.id) ? "checked" : ""}></td><td class="cell-title"><b>${esc(item.sap)}</b><small>${esc(item.name)}</small>${recipeNotice(item) ? `<em class="recipe-note">${esc(recipeNotice(item))}</em>` : ""}</td><td>${esc(item.category)}</td><td>${esc(item.code || "Pendiente")}</td><td>${esc(item.woe || "Pendiente")}</td><td>${formatNumber(item.usage, 1)}</td><td><b>${formatMinMax(calc.min, calc.mode)}</b></td><td><b>${formatMinMax(calc.max, calc.mode)}</b></td></tr>`;
  }).join("") || '<tr><td colspan="8" class="empty-state">Sin insumos con uso mayor a cero.</td></tr>';
}

function positiveReportItems() {
  return state.filtered.filter((item) => {
    const calc = calculate(item);
    return Number(item.usage) > 0 && Number(calc.min) > 0 && Number(calc.max) > 0;
  });
}

function onCatalogChange(event) {
  if (!(event.target instanceof HTMLInputElement)) return;
  const id = Number(event.target.value);
  if (event.target.checked) state.selected.add(id); else state.selected.delete(id);
  state.previewPage = Math.max(0, Math.ceil(state.selected.size / PAGE_SIZE) - 1);
  renderAll();
}

function onConsultaChange(event) {
  const id = Number(event.target.dataset.id);
  if (!Number.isFinite(id)) return;
  if (event.target.classList.contains("row-select")) {
    if (event.target.checked) state.selected.add(id); else state.selected.delete(id);
  }
  renderAll();
}

function selectFiltered() {
  const items = positiveReportItems();
  state.selected = new Set(items.map((item) => item.id));
  state.previewPage = Math.max(0, Math.ceil(state.selected.size / PAGE_SIZE) - 1);
  renderAll();
  toast(`${items.length} ingrediente(s) visibles seleccionados.`);
}


function addAcomodoItems() {
  const candidates = state.filtered.filter((item) => Number(item.usage) > 0);
  if (!candidates.length) { toast("No hay artículos con uso para agregar. Ajusta los filtros."); return; }
  const chosen = candidates.slice(0, ACOMODO_MAX_ITEMS);
  state.selected = new Set(chosen.map((item) => item.id));
  activeMarkerId = chosen[0]?.id || null;
  persistState();
  renderAll();
  toast(candidates.length > ACOMODO_MAX_ITEMS
    ? `Se agregaron los primeros ${ACOMODO_MAX_ITEMS}. Acota el filtro para elegir otros.`
    : `${chosen.length} artículo(s) agregados al rack.`);
}

function clearAcomodoItems() {
  state.selected.clear();
  activeMarkerId = null;
  if (state.store) state.markerPositions[state.store.code] = {};
  persistState();
  renderAll();
}

function clearSelection() { state.selected.clear(); state.previewPage = 0; renderAll(); }

function resetFilters() {
  state.categories.clear();
  state.ingredients.clear();
  state.weeks = new Set(latestWeeks(8));
  weeksFilter = rebuildWeeksFilter();
  categoriesFilter.render();
  ingredientsFilter.render();
  state.catalogSearch = "";
  $("catalogSearch").value = "";
  aggregateData();
  persistState();
}

function setWeekPreset(preset) {
  const amount = preset === "latest" ? 1 : Number(preset);
  state.weeks = new Set(latestWeeks(amount));
  weeksFilter = rebuildWeeksFilter();
  aggregateData();
  persistState();
  toast(`Semanas seleccionadas: ${compactWeeks([...state.weeks])}`);
}

function rebuildWeeksFilter() {
  $("weeksFilter").innerHTML = "";
  return createMultiFilter($("weeksFilter"), {
    label: "Semanas", searchable: false,
    options: manifest.weeks.map((week) => ({ value: week, label: `Semana ${week}` })),
    selected: state.weeks,
    onChange: () => { aggregateData(); persistState(); },
  });
}

function resetCurrent() {
  if (state.tab === "etiquetas") clearSelection();
  else if (state.tab === "consulta") resetFilters();
  else { state.markerPositions[state.store.code] = {}; clearPhoto(); renderMarkers(); persistState(); }
}

function selectedItemsCurrent() {
  const byId = new Map(state.aggregated.map((item) => [item.id, item]));
  return [...state.selected].map((id) => byId.get(id)).filter((item) => item && Number(item.usage) > 0 && calculate(item).min > 0 && calculate(item).max > 0);
}

function onPhotoChange(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const image = $("rackPhoto");
  if (rackPhotoUrl) URL.revokeObjectURL(rackPhotoUrl);
  rackPhotoUrl = URL.createObjectURL(file);
  image.onload = () => { $("photoStage").classList.add("has-photo"); $("enhancePhotoButton").disabled = false; renderMarkers(); };
  image.src = rackPhotoUrl;
}

function clearPhoto() {
  $("photoInput").value = "";
  $("photoCameraInput").value = "";
  $("rackPhoto").removeAttribute("src");
  $("photoStage").classList.remove("has-photo", "enhanced");
  $("enhancePhotoButton").disabled = true;
  $("enhancePhotoButton").textContent = "Nitidez";
  if (rackPhotoUrl) URL.revokeObjectURL(rackPhotoUrl);
  rackPhotoUrl = undefined;
  updateWorkflowProgress();
}

function togglePhotoEnhancement() {
  const enhanced = $("photoStage").classList.toggle("enhanced");
  $("enhancePhotoButton").textContent = enhanced ? "Nitidez aplicada" : "Nitidez";
}

function renderMarkers() {
  if (!state.store) return;
  const allSelected = selectedItemsCurrent();
  const items = allSelected.slice(0, ACOMODO_MAX_ITEMS);
  if (activeMarkerId && !items.some((item) => item.id === activeMarkerId)) activeMarkerId = null;
  const positions = state.markerPositions[state.store.code] || (state.markerPositions[state.store.code] = {});
  $("markerCount").textContent = `${items.length} / ${ACOMODO_MAX_ITEMS}`;
  $("acomodoSelectionHint").textContent = items.length
    ? `${items.length} artículo(s) elegidos · ${state.orders} pedidos`
    : "El usuario decide cuáles incluir · máximo 25.";
  $("markerList").innerHTML = items.map((item, index) => {
    const calc = calculate(item);
    return `<button class="marker-row ${activeMarkerId === item.id ? "active" : ""}" type="button" draggable="true" data-marker-id="${item.id}" aria-pressed="${activeMarkerId === item.id}"><span class="marker-number">${index + 1}</span><span class="marker-identity"><b>${esc(item.sap)}</b><small>${esc(item.name)}</small><em>Toca y ubica en la foto</em></span><strong>${formatNumber(item.usage, 1)}</strong><strong>${formatMinMax(calc.min, calc.mode)}</strong><strong>${formatMinMax(calc.max, calc.mode)}</strong></button>`;
  }).join("") || '<div class="empty-state">Elige ingredientes en el filtro y usa “Agregar artículos filtrados”.</div>';
  const layer = $("markerLayer");
  layer.innerHTML = "";
  items.forEach((item, index) => {
    const defaultPosition = { x: 5 + (index % 10) * 9.5, y: 7 + Math.floor(index / 10) * 11 };
    const position = positions[item.id] || defaultPosition;
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = `marker ${activeMarkerId === item.id ? "active" : ""}`;
    marker.dataset.markerId = String(item.id);
    marker.textContent = String(index + 1);
    marker.title = item.sap || item.name;
    marker.style.left = `${position.x}%`;
    marker.style.top = `${position.y}%`;
    bindMarkerDrag(marker, item.id, positions);
    layer.appendChild(marker);
  });
  if (allSelected.length > ACOMODO_MAX_ITEMS) toast(`Acomodo admite hasta ${ACOMODO_MAX_ITEMS} artículos. Ajusta tu selección.`);
  updateWorkflowProgress();
}

function activateMarker(ingredientId) {
  activeMarkerId = Number(ingredientId);
  document.querySelectorAll("[data-marker-id]").forEach((element) => {
    const active = Number(element.dataset.markerId) === activeMarkerId;
    element.classList.toggle("active", active);
    if (element.classList.contains("marker-row")) element.setAttribute("aria-pressed", String(active));
  });
}

function onMarkerListClick(event) {
  const row = event.target.closest(".marker-row");
  if (!row) return;
  activateMarker(row.dataset.markerId);
  if (!$("photoStage").classList.contains("has-photo")) toast("Toma o adjunta una foto; después toca la ubicación del insumo.");
}

function onMarkerListDragStart(event) {
  const row = event.target.closest(".marker-row");
  if (!row || !event.dataTransfer) return;
  activateMarker(row.dataset.markerId);
  event.dataTransfer.effectAllowed = "move";
  event.dataTransfer.setData("text/plain", row.dataset.markerId);
}

function onPhotoStageDragOver(event) {
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = "move";
  $("photoStage").classList.add("drop-ready");
}

function onPhotoStageDrop(event) {
  event.preventDefault();
  $("photoStage").classList.remove("drop-ready");
  const ingredientId = Number(event.dataTransfer?.getData("text/plain") || activeMarkerId);
  if (!Number.isFinite(ingredientId)) return;
  placeMarkerAt(ingredientId, event.clientX, event.clientY);
}

function onPhotoStageClick(event) {
  if (event.target.closest(".marker") || !activeMarkerId) return;
  if (!$("photoStage").classList.contains("has-photo")) { toast("Primero toma o adjunta la foto de la estación."); return; }
  placeMarkerAt(activeMarkerId, event.clientX, event.clientY);
}

function placeMarkerAt(ingredientId, clientX, clientY) {
  const rect = $("markerLayer").getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = Math.max(0, Math.min(92, ((clientX - rect.left - 21) / rect.width) * 100));
  const y = Math.max(0, Math.min(92, ((clientY - rect.top - 17) / rect.height) * 100));
  const positions = state.markerPositions[state.store.code] || (state.markerPositions[state.store.code] = {});
  positions[ingredientId] = { x, y };
  activeMarkerId = ingredientId;
  persistState();
  renderMarkers();
}

function bindMarkerDrag(marker, ingredientId, positions) {
  let active = false;
  marker.addEventListener("pointerdown", (event) => { active = true; activateMarker(ingredientId); marker.classList.add("dragging"); marker.setPointerCapture(event.pointerId); });
  marker.addEventListener("pointermove", (event) => {
    if (!active) return;
    const rect = $("markerLayer").getBoundingClientRect();
    const x = Math.max(0, Math.min(92, ((event.clientX - rect.left - marker.offsetWidth / 2) / rect.width) * 100));
    const y = Math.max(0, Math.min(92, ((event.clientY - rect.top - marker.offsetHeight / 2) / rect.height) * 100));
    positions[ingredientId] = { x, y };
    marker.style.left = `${x}%`; marker.style.top = `${y}%`;
  });
  const stop = () => { if (!active) return; active = false; marker.classList.remove("dragging"); persistState(); };
  marker.addEventListener("pointerup", stop); marker.addEventListener("pointercancel", stop);
}

async function exportPdf() {
  const items = selectedItemsCurrent();
  if (!items.length) { toast("Selecciona al menos un ingrediente antes de exportar."); return; }
  if (!window.jspdf?.jsPDF) { toast("El motor PDF local no está disponible."); return; }
  showLoading("Renderizando PDF", `${items.length} etiqueta(s) · Carta horizontal`);
  await new Promise((resolve) => setTimeout(resolve, 80));
  try {
    const pdf = buildPdf(items);
    const expectedPages = Math.ceil(items.length / PAGE_SIZE);
    if (pdf.internal.getNumberOfPages() !== expectedPages) throw new Error("Número de páginas inesperado");
    if (pdf.internal.pageSize.getWidth() <= pdf.internal.pageSize.getHeight()) throw new Error("Orientación inválida");
    const filename = `${safeName(state.store.label)}_Sem_${safeName(compactWeeks([...state.weeks]))}_Etiquetas_MIN_MAX.pdf`;
    pdf.save(filename);
    $("exportSummary").textContent = `${items.length} etiquetas · ${expectedPages} hoja(s) Carta.`;
    $("exportDialog").showModal();
  } catch (error) {
    console.error(error);
    toast("La validación detuvo el PDF. Revisa los datos e intenta nuevamente.");
  } finally { hideLoading(); }
}

function listItemsCurrent() {
  return positiveReportItems();
}

function openExportConfirmation(kind = "labels") {
  const items = kind === "list" ? listItemsCurrent() : selectedItemsCurrent();
  if (!items.length) { toast(kind === "list" ? "No hay filas con uso mayor a cero." : "Selecciona al menos un ingrediente."); return; }
  if (kind === "acomodo" && !$("photoStage").classList.contains("has-photo")) { toast("Toma o adjunta la foto del rack antes de exportar."); return; }
  if (!window.jspdf?.jsPDF) { toast("El motor PDF local no está disponible."); return; }
  pendingExportKind = kind;
  const exportItems = kind === "acomodo" ? items.slice(0, ACOMODO_MAX_ITEMS) : items;
  const pageSize = kind === "list" ? LIST_PAGE_SIZE : kind === "acomodo" ? ACOMODO_PAGE_SIZE : PAGE_SIZE;
  const pages = Math.ceil(exportItems.length / pageSize);
  const outputLabel = kind === "list" ? "filas en lista operativa" : kind === "acomodo" ? "artículos en acomodo" : "etiquetas de rack";
  $("confirmExportSummary").textContent = `${state.store.label} · Sem ${compactWeeks([...state.weeks])} · ${state.orders} pedidos · ${exportItems.length} ${outputLabel} · ${pages} hoja(s) Carta.`;
  $("confirmExportButton").textContent = kind === "list" ? "Exportar lista" : kind === "acomodo" ? "Exportar acomodo" : "Exportar etiquetas";
  $("confirmExportDialog").showModal();
}

function runConfirmedExport() {
  if (pendingExportKind === "list") exportListPdf();
  else if (pendingExportKind === "acomodo") exportAcomodoPdf();
  else exportPdf();
}

async async function exportAcomodoPdf() {
  const items = selectedItemsCurrent().slice(0, ACOMODO_MAX_ITEMS);
  if (!items.length || !$("photoStage").classList.contains("has-photo")) { toast("Acomodo necesita foto y al menos un artículo."); return; }
  showLoading("Renderizando acomodo", `${items.length} artículo(s) · ${state.orders} pedidos`);
  await new Promise((resolve) => setTimeout(resolve, 80));
  try {
    const pdf = buildAcomodoPdf(items, rackPhotoDataUrl());
    const expectedPages = Math.ceil(items.length / ACOMODO_PAGE_SIZE);
    if (pdf.internal.getNumberOfPages() !== expectedPages) throw new Error("Paginación inesperada en Acomodo");
    const filename = `${safeName(state.store.label)}_Sem_${safeName(compactWeeks([...state.weeks]))}_Acomodo.pdf`;
    pdf.save(filename);
    $("exportSummary").textContent = `${items.length} artículos · ${expectedPages} hoja(s) Carta · ${state.orders} pedidos.`;
    $("exportDialog").showModal();
  } catch (error) {
    console.error(error);
    toast("La validación detuvo el PDF de Acomodo. Revisa la foto e intenta nuevamente.");
  } finally { hideLoading(); }
}

function rackPhotoDataUrl() {
  const image = $("rackPhoto");
  const canvas = document.createElement("canvas");
  const maxWidth = 1800;
  const scale = Math.min(1, maxWidth / image.naturalWidth);
  canvas.width = Math.max(1, Math.round(image.naturalWidth * scale));
  canvas.height = Math.max(1, Math.round(image.naturalHeight * scale));
  const context = canvas.getContext("2d");
  context.filter = $("photoStage").classList.contains("enhanced") ? "contrast(1.08) saturate(1.04) brightness(1.02)" : "none";
  context.drawImage(image, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.88);
}

function buildAcomodoPdf(items, photoData) {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: "mm", format: "letter", orientation: "landscape", compress: true, putOnlyUsedFonts: true });
  pdf.setProperties({ title: "Acomodo de rack MIN MAX", subject: `${pdfSafeText(state.store.label)} - ${state.orders} pedidos`, creator: "Max & Min Remaster" });
  const width = pdf.internal.pageSize.getWidth();
  const height = pdf.internal.pageSize.getHeight();
  const margin = 6;
  const pages = Math.ceil(items.length / ACOMODO_PAGE_SIZE);
  const properties = pdf.getImageProperties(photoData);
  const photoY = 15;
  const photoH = 112;
  const photoW = width - margin * 2;
  const scale = Math.min(photoW / properties.width, photoH / properties.height);
  const drawW = properties.width * scale;
  const drawH = properties.height * scale;
  const columns = [10, 150, 30, 30, 30];
  const headers = ["#", "INGREDIENTE / SAP", "USO PROM. SEM", "MÍN.", "MÁX."];

  for (let pageIndex = 0; pageIndex < pages; pageIndex += 1) {
    if (pageIndex) pdf.addPage("letter", "landscape");
    pdf.setFillColor(255,255,255); pdf.rect(0,0,width,height,"F");
    drawPdfHeader(pdf, margin, 4, width - margin * 2, 8);
    pdf.setFillColor(244,248,246); pdf.roundedRect(margin,photoY,photoW,photoH,2,2,"F");
    pdf.addImage(photoData,"JPEG",margin+(photoW-drawW)/2,photoY+(photoH-drawH)/2,drawW,drawH,undefined,"FAST");
    const listY=132;
    let cursor=margin;
    pdf.setFillColor(0,59,42); pdf.rect(margin,listY,columns.reduce((a,b)=>a+b,0),7,"F");
    pdf.setTextColor(255,255,255); pdf.setFont("helvetica","bold"); pdf.setFontSize(5.8);
    headers.forEach((label,index)=>{pdf.text(label,cursor+1.5,listY+4.7);cursor+=columns[index];});
    const pageItems=items.slice(pageIndex*ACOMODO_PAGE_SIZE,(pageIndex+1)*ACOMODO_PAGE_SIZE);
    pageItems.forEach((item,index)=>{
      const calc=calculate(item);
      const y=listY+7+index*8.6;
      pdf.setFillColor(index%2?247:255,index%2?250:255,index%2?248:255);
      pdf.setDrawColor(218,229,224); pdf.rect(margin,y,columns.reduce((a,b)=>a+b,0),8.6,"FD");
      const values=[String(pageIndex*ACOMODO_PAGE_SIZE+index+1),`${pdfSafeText(item.sap)} | ${pdfSafeText(item.name)}`,formatNumber(item.usage,1),formatMinMax(calc.min,calc.mode),formatMinMax(calc.max,calc.mode)];
      let x=margin;
      values.forEach((value,columnIndex)=>{const columnW=columns[columnIndex];if(columnIndex)pdf.line(x,y,x,y+8.6);pdf.setTextColor(24,35,31);pdf.setFont("helvetica",columnIndex===1?"bold":"normal");fitPdfFont(pdf,value,columnW-3,6.1,4.6);pdf.text(fitPdfText(pdf,value,columnW-3),x+1.5,y+5.5);x+=columnW;});
    });
    pdf.setTextColor(100,116,109);pdf.setFont("helvetica","normal");pdf.setFontSize(5.5);
    pdf.text(`Hoja ${pageIndex+1} de ${pages}`,width/2,height-3.2,{align:"center"});
    pdf.text("Sistema de Evidencias OPS - Max & Min",width-margin,height-3.2,{align:"right"});
  }
  return pdf;
}

function buildListPdf(items) {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: "mm", format: "letter", orientation: "landscape", compress: true, putOnlyUsedFonts: true });
  pdf.setProperties({ title: "Lista operativa MIN MAX", subject: `${pdfSafeText(state.store.label)} - Semanas ${compactWeeks([...state.weeks])}`, creator: "Max & Min Remaster" });
  const width = pdf.internal.pageSize.getWidth();
  const height = pdf.internal.pageSize.getHeight();
  const margin = 6;
  const tableY = 14.5;
  const rowH = 8.5;
  const columns = [
    ["INGREDIENTE / SAP", 86], ["CATEGORÍA", 39], ["#DIA", 18], ["#SAP", 20],
    ["USO PROM. SEM", 25], ["MÍN.", 18], ["MÁX.", 18], ["# PEDIDOS", width - margin * 2 - 224],
  ];
  const pages = Math.ceil(items.length / LIST_PAGE_SIZE);

  for (let pageIndex = 0; pageIndex < pages; pageIndex += 1) {
    if (pageIndex) pdf.addPage("letter", "landscape");
    pdf.setFillColor(255,255,255); pdf.rect(0,0,width,height,"F");
    drawPdfHeader(pdf,margin,4,width-margin*2,8);
    drawListTableHeader(pdf,columns,margin,tableY);
    const pageItems=items.slice(pageIndex*LIST_PAGE_SIZE,(pageIndex+1)*LIST_PAGE_SIZE);
    pageItems.forEach((item,rowIndex)=>drawListRow(pdf,columns,item,margin,tableY+7+rowIndex*rowH,rowH,rowIndex));
    pdf.setTextColor(100,116,109);pdf.setFont("helvetica","normal");pdf.setFontSize(5.5);
    pdf.text(`Hoja ${pageIndex+1} de ${pages}`,width/2,height-3.2,{align:"center"});
    pdf.text("Sistema de Evidencias OPS - Max & Min",width-margin,height-3.2,{align:"right"});
  }
  return pdf;
}

function drawListTableHeader(pdf, columns, x, y) {
  let cursor = x;
  pdf.setFillColor(0, 59, 42); pdf.setDrawColor(0, 59, 42); pdf.rect(x, y, columns.reduce((sum, column) => sum + column[1], 0), 7, "FD");
  pdf.setTextColor(255, 255, 255); pdf.setFont("helvetica", "bold"); pdf.setFontSize(5.6);
  columns.forEach(([label, columnWidth]) => { pdf.text(label, cursor + 1.5, y + 4.6); cursor += columnWidth; });
}

function drawListRow(pdf, columns, item, x, y, rowHeight, rowIndex) {
  const calc = calculate(item);
  const values = [
    `${pdfSafeText(item.sap)} - ${pdfSafeText(item.name)}`, pdfSafeText(item.category), item.code || "Pendiente", item.woe || "Pendiente",
    formatNumber(item.usage,1), formatMinMax(calc.min,calc.mode), formatMinMax(calc.max,calc.mode), String(state.orders),
  ];
  const totalWidth=columns.reduce((sum,column)=>sum+column[1],0);
  pdf.setFillColor(rowIndex%2?247:255,rowIndex%2?250:255,rowIndex%2?248:255);
  pdf.setDrawColor(218,229,224);pdf.rect(x,y,totalWidth,rowHeight,"FD");
  let cursor=x;
  values.forEach((value,columnIndex)=>{const columnWidth=columns[columnIndex][1];if(columnIndex)pdf.line(cursor,y,cursor,y+rowHeight);pdf.setTextColor(27,43,36);pdf.setFont("helvetica",columnIndex===0||columnIndex>=4?"bold":"normal");fitPdfFont(pdf,value,columnWidth-3,5.9,4.7);const align=columnIndex===7?"center":"left";pdf.text(fitPdfText(pdf,value,columnWidth-3),align==="center"?cursor+columnWidth/2:cursor+1.5,y+5.3,{align});cursor+=columnWidth;});
}

function buildPdf(items) {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: "mm", format: "letter", orientation: "landscape", compress: true, putOnlyUsedFonts: true });
  pdf.setProperties({ title: "Etiquetas MIN MAX", subject: `${pdfSafeText(state.store.label)} - Semanas ${compactWeeks([...state.weeks])}`, creator: "Max & Min Remaster" });
  const width = pdf.internal.pageSize.getWidth();
  const height = pdf.internal.pageSize.getHeight();
  const margin = 6;
  const headerY = 4;
  const headerH = 8;
  const gridY = headerY + headerH + 2.4;
  const bottom = 4.5;
  const gapX = 2.6;
  const gapY = 2.4;
  const cardW = (width - margin * 2 - gapX * 2) / 3;
  const cardH = (height - gridY - bottom - gapY * 3) / 4;
  const pages = Math.ceil(items.length / PAGE_SIZE);

  for (let pageIndex = 0; pageIndex < pages; pageIndex += 1) {
    if (pageIndex) pdf.addPage("letter", "landscape");
    pdf.setFillColor(255, 255, 255); pdf.rect(0, 0, width, height, "F");
    drawPdfHeader(pdf, margin, headerY, width - margin * 2, headerH);
    const pageItems = items.slice(pageIndex * PAGE_SIZE, (pageIndex + 1) * PAGE_SIZE);
    pageItems.forEach((item, index) => {
      const row = Math.floor(index / 3);
      const col = index % 3;
      drawPdfLabel(pdf, item, margin + col * (cardW + gapX), gridY + row * (cardH + gapY), cardW, cardH);
    });
  }
  return pdf;
}

function drawPdfHeader(pdf, x, y, width, height) {
  const values = [
    ["TIENDA", pdfSafeText(state.store.label)],
    ["SEMANAS", compactWeeks([...state.weeks])],
    ["ACTUALIZACIÓN", formatDate(manifest.generated)],
    ["PEDIDOS", String(state.orders)],
  ];
  const widths = [width * .38, width * .22, width * .25, width * .15];
  pdf.setDrawColor(0, 98, 65); pdf.setLineWidth(.3); pdf.roundedRect(x, y, width, height, 1.5, 1.5, "S");
  let sx = x;
  values.forEach(([label, value], index) => {
    const sectionW = widths[index];
    if (index) pdf.line(sx, y, sx, y + height);
    pdf.setTextColor(0, 98, 65); pdf.setFont("helvetica", "bold"); pdf.setFontSize(5.6);
    const labelText = `${label}:`;
    pdf.text(labelText, sx + 2.5, y + 5.15);
    const valueX = sx + 2.5 + pdf.getTextWidth(labelText) + 1.4;
    const available = sectionW - (valueX - sx) - 2.5;
    pdf.setTextColor(24, 35, 31); pdf.setFont("helvetica", "bold");
    fitPdfFont(pdf, value, available, 7.4, 5.8);
    pdf.text(fitPdfText(pdf, value, available), valueX, y + 5.15);
    sx += sectionW;
  });
}

function drawPdfLabel(pdf, item, x, y, width, height) {
  const calc = calculate(item);
  const topH = Math.max(20.5, height * .42);
  const footerH = 7.2;
  const bodyY = y + topH;
  const bodyH = height - topH - footerH;
  pdf.setDrawColor(22, 31, 28); pdf.setLineWidth(.45); pdf.setFillColor(255, 255, 255); pdf.roundedRect(x, y, width, height, 2, 2, "FD");
  pdf.setDrawColor(22, 31, 28); pdf.line(x, bodyY, x + width, bodyY); pdf.line(x + width / 2, bodyY, x + width / 2, bodyY + bodyH); pdf.line(x, y + height - footerH, x + width, y + height - footerH);
  pdf.setDrawColor(188, 199, 194); pdf.setLineWidth(.25); pdf.line(x + width / 3, y + height - footerH, x + width / 3, y + height); pdf.line(x + width * 2 / 3, y + height - footerH, x + width * 2 / 3, y + height);
  pdf.setTextColor(20, 29, 26); pdf.setFont("helvetica", "bold");
  drawFittedLines(pdf, pdfSafeText(item.sap), x + 3, y + 2.2, width - 6, topH - 8.2, 10.4, 6.2, 2);
  const identity = `${pdfSafeText(item.name)} | #DIA ${item.code || "-"} | #SAP ${item.woe || "-"}`;
  pdf.setDrawColor(218, 225, 222); pdf.setLineWidth(.2); pdf.line(x + 3, y + topH - 6.4, x + width - 3, y + topH - 6.4);
  pdf.setTextColor(72, 88, 81); pdf.setFont("helvetica", "normal"); fitPdfFont(pdf, identity, width - 6, 6.1, 4.8);
  pdf.text(fitPdfText(pdf, identity, width - 6), x + width / 2, y + topH - 2.15, { align: "center" });

  const centers = [x + width / 4, x + width * .75];
  [["MIN", calc.min], ["MAX", calc.max]].forEach(([label, value], index) => {
    pdf.setTextColor(22, 31, 28); pdf.setFont("helvetica", "bold"); pdf.setFontSize(8.2); pdf.text(label, centers[index], bodyY + 6.2, { align: "center" });
    pdf.setFontSize(Math.min(18.5, bodyH * 1.05)); pdf.text(formatMinMax(value, calc.mode), centers[index], bodyY + bodyH - 3.8, { align: "center" });
  });
  pdf.setTextColor(0, 98, 65); pdf.setFont("helvetica", "bold");
  const mode = calc.mode === "pickpack" ? "PICK PACK" : "UNIDAD";
  fitPdfFont(pdf, mode, width / 3 - 4, 6.2, 5);
  pdf.text(mode, x + width / 6, y + height - 2.45, { align: "center" });
  pdf.setTextColor(85, 101, 94); pdf.setFont("helvetica", "normal");
  fitPdfFont(pdf, calc.presentation, width / 3 - 4, 6, 4.8);
  pdf.text(fitPdfText(pdf, calc.presentation, width / 3 - 4), x + width / 2, y + height - 2.45, { align: "center" });
  const ordersText = `${state.orders} PEDIDOS`;
  pdf.setFont("helvetica", "bold"); fitPdfFont(pdf, ordersText, width / 3 - 4, 6.2, 5); pdf.text(ordersText, x + width * 5 / 6, y + height - 2.45, { align: "center" });
}

function fitPdfFont(pdf, value, maxWidth, preferred, minimum) {
  let size = preferred;
  pdf.setFontSize(size);
  while (size > minimum && pdf.getTextWidth(String(value)) > maxWidth) { size -= .2; pdf.setFontSize(size); }
  return size;
}

function fitPdfText(pdf, value, maxWidth) {
  const original = String(value || "");
  if (pdf.getTextWidth(original) <= maxWidth) return original;
  let fitted = original;
  while (fitted.length > 1 && pdf.getTextWidth(`${fitted}...`) > maxWidth) fitted = fitted.slice(0, -1);
  return `${fitted}...`;
}

function drawFittedLines(pdf, value, x, y, width, height, preferred, minimum, maxLines) {
  let size = preferred;
  let lines = [];
  do {
    pdf.setFontSize(size);
    lines = pdf.splitTextToSize(String(value || ""), width);
    if (lines.length <= maxLines && lines.length * size * .36 <= height) break;
    size -= .25;
  } while (size > minimum);
  lines = lines.slice(0, maxLines);
  if (lines.length === maxLines) lines[maxLines - 1] = fitPdfText(pdf, lines[maxLines - 1], width);
  pdf.text(lines, x, y + size * .35, { baseline: "top" });
}

function updateHealth() {
  const counts = manifest.counts;
  const total = Number(counts.ingredients || 0);
  const matched = Number(counts.sapMatched || 0);
  $("healthBadge").textContent = `Datos hasta Sem ${manifest.weeks.at(-1)} · ${matched}/${total} SAP · ${counts.storesWithData} tiendas`;
}

async function fetchStoreData(path, version = manifest.generated) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const separator = path.includes("?") ? "&" : "?";
      const response = await fetch(`${path}${separator}v=${encodeURIComponent(version)}`, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 350));
    } finally { clearTimeout(timeout); }
  }
  throw lastError;
}

function openSupportPdf(event) {
  event.preventDefault();
  const link = event.currentTarget;
  $("supportPdfTitle").textContent = link.textContent.trim() || "Guía de apoyo";
  $("supportPdfFrame").src = link.getAttribute("href");
  $("supportPdfDialog").showModal();
}

function latestWeeks(amount) {
  return manifest.weeks.slice(-Math.max(1, Number(amount) || 1));
}

function compactWeeks(values) {
  const sorted = [...new Set(values.map(Number))].sort((a, b) => a - b);
  if (!sorted.length) return "-";
  const ranges = [];
  let start = sorted[0]; let end = sorted[0];
  for (let index = 1; index <= sorted.length; index += 1) {
    const current = sorted[index];
    if (current === end + 1) { end = current; continue; }
    ranges.push(start === end ? String(start) : `${start}-${end}`);
    start = current; end = current;
  }
  return ranges.join(", ");
}

function cleanPresentation(value) {
  const cleaned = String(value || "Unidad").replace(/\s+/g, " ").replace(/^([A-ZÁÉÍÓÚÑ0-9]+):\s*/i, "").trim();
  return cleaned || "Unidad";
}

function pdfSafeText(value) { return String(value || "").replace(/[·•–—]/g, "-"); }
function round1(value) { return Math.round((Number(value) || 0) * 10) / 10; }
function formatMinMax(value, mode) { return Number(value || 0).toLocaleString("es-MX", { minimumFractionDigits: mode === "unidad" ? 1 : 0, maximumFractionDigits: mode === "unidad" ? 1 : 0 }); }
function formatNumber(value, digits = 0) { return Number(value || 0).toLocaleString("es-MX", { maximumFractionDigits: digits }); }
function formatDate(value) { const [year, month, day] = String(value).split("-"); return year && month && day ? `${day}/${month}/${year}` : String(value); }
function normalize(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/\s+/g, " ").trim(); }
function safeName(value) { return normalize(value).replace(/[^a-z0-9]+/g, "_").replace(/^_|_$/g, ""); }
function esc(value) { return String(value ?? "").replace(/[&<>\"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char])); }

function showLoading(title, detail) { $("loadingTitle").textContent = title; $("loadingText").textContent = detail; $("loadingOverlay").classList.remove("hidden"); }
function hideLoading() { $("loadingOverlay").classList.add("hidden"); }
function toast(message) { clearTimeout(toastTimer); $("toast").textContent = message; $("toast").classList.remove("hidden"); toastTimer = setTimeout(() => $("toast").classList.add("hidden"), 4200); }

window.addEventListener("DOMContentLoaded", init);
