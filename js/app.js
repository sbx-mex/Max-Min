"use strict";

const FACTOR_PEDIDOS = { 2: 5, 3: 4, 4: 3, 5: 2 };
const STORAGE_KEY = "maxmin-remaster-v4";
const PAGE_SIZE = 12;
const $ = (id) => document.getElementById(id);
const manifest = window.MAXMIN_MANIFEST;

const state = {
  tab: "etiquetas",
  store: null,
  storeData: null,
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
let toastTimer;

function init() {
  if (!manifest || !Array.isArray(manifest.stores) || !manifest.stores.length) {
    document.body.innerHTML = "<main class='app-shell'><section class='card empty-state'>No se pudo cargar el manifiesto de datos. Ejecuta la auditoría del proyecto.</section></main>";
    return;
  }
  restoreState();
  $("versionRange").textContent = `Remaster · Semanas ${manifest.weeks.at(0)}-${manifest.weeks.at(-1)}`;
  buildStoreOptions();
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

function buildStoreOptions() {
  $("storeOptions").innerHTML = manifest.stores.map((store) => `<option value="${esc(store.label)}"></option>`).join("");
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
  $("storeInput").addEventListener("change", onStoreInput);
  $("storeInput").addEventListener("keydown", (event) => { if (event.key === "Enter") { event.preventDefault(); onStoreInput(); } });
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
  $("exportButton").addEventListener("click", openExportConfirmation);
  $("previousPreview").addEventListener("click", () => { state.previewPage = Math.max(0, state.previewPage - 1); renderPreview(); });
  $("nextPreview").addEventListener("click", () => { state.previewPage += 1; renderPreview(); });
  $("catalogList").addEventListener("change", onCatalogChange);
  $("consultaBody").addEventListener("change", onConsultaChange);
  $("photoInput").addEventListener("change", onPhotoChange);
  $("clearPhotoButton").addEventListener("click", clearPhoto);
  $("cancelExportButton").addEventListener("click", () => $("confirmExportDialog").close());
  $("confirmExportButton").addEventListener("click", () => { $("confirmExportDialog").close(); exportPdf(); });
  $("closeExportDialog").addEventListener("click", () => $("exportDialog").close());
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") document.querySelectorAll(".filter-menu").forEach((menu) => menu.classList.add("hidden"));
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("catalogSearch").focus(); }
  });
}

function setTab(tab) {
  state.tab = tab;
  document.querySelectorAll(".tab").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `tab-${tab}`));
  persistState();
  renderAll();
}

function onStoreInput() {
  const raw = $("storeInput").value.trim();
  const code = raw.match(/^\d{3,6}/)?.[0];
  const store = manifest.stores.find((item) => item.label === raw || item.code === code)
    || manifest.stores.find((item) => normalize(item.label).includes(normalize(raw)));
  if (!store) { toast("Selecciona una tienda válida del Directorio."); $("storeInput").value = state.store?.label || ""; return; }
  selectStore(store, true);
}

async function selectStore(store, notify) {
  if (state.store?.code === store.code && state.storeData) return;
  showLoading("Cargando tienda", `${store.code} · ${store.name}`);
  try {
    state.storeData = await fetchStoreData(store.file);
    state.store = store;
    state.categories.clear();
    state.ingredients.clear();
    state.selected.clear();
    state.previewPage = 0;
    $("storeInput").value = store.label;
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
  const divisor = selectedWeeks.length || 1;
  const map = new Map();
  for (const week of selectedWeeks) {
    const flat = state.storeData[String(week)] || [];
    for (let index = 0; index < flat.length; index += 3) {
      const categoryId = flat[index];
      const ingredientId = flat[index + 1];
      const cents = flat[index + 2];
      let item = map.get(ingredientId);
      if (!item) {
        item = { id: ingredientId, categoryId, cents: 0, weeksWithUsage: 0 };
        map.set(ingredientId, item);
      }
      item.cents += cents;
      item.weeksWithUsage += cents > 0 ? 1 : 0;
    }
  }
  state.aggregated = [...map.values()].map((item) => ({
    ...item,
    ...manifest.ingredients[item.id],
    category: manifest.categories[item.categoryId],
    usage: item.cents / 100 / divisor,
  })).sort((a, b) => a.name.localeCompare(b.name, "es", { numeric: true }));
  const categoryOptions = [...new Map(state.aggregated.map((item) => [item.categoryId, item.category])).entries()]
    .sort((a, b) => a[1].localeCompare(b[1], "es"))
    .map(([value, label]) => ({ value, label }));
  categoriesFilter.setOptions(categoryOptions);
  updateIngredientOptions();
  applyFilters();
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
  $("filteredCount").textContent = String(state.filtered.length);
  const items = state.filtered.slice(0, 300);
  $("catalogList").innerHTML = items.map((item) => `<label class="catalog-item ${state.selected.has(item.id) ? "selected" : ""}"><input type="checkbox" value="${item.id}" ${state.selected.has(item.id) ? "checked" : ""} /><span class="catalog-copy"><b>${esc(item.name)}</b><small>${esc(item.sap)}${item.code ? ` · DIA ${esc(item.code)}` : ""}</small></span><span class="usage-badge">${formatNumber(item.usage, 1)}</span></label>`).join("") || '<div class="empty-state">No hay ingredientes con estos filtros.</div>';
  if (state.filtered.length > 300) $("catalogList").insertAdjacentHTML("beforeend", `<div class="empty-state">Mostrando 300 de ${state.filtered.length}. Usa la búsqueda para acotar.</div>`);
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
  $("exportButton").disabled = !selected.length;
}

function labelCardHtml(item) {
  const calc = calculate(item);
  const dia = item.code || "—";
  const sapNumber = item.woe || "—";
  return `<article class="label-card"><div class="label-name"><b title="${esc(item.sap)}">${esc(item.sap)}</b><small><span title="Nombre Inventario">${esc(item.name)}</span><span>#DIA ${esc(dia)}</span><span>#SAP ${esc(sapNumber)}</span></small></div><div class="label-values"><span class="label-value"><small>MIN</small><b>${formatMinMax(calc.min, calc.mode)}</b></span><span class="label-value"><small>MAX</small><b>${formatMinMax(calc.max, calc.mode)}</b></span></div><div class="label-meta"><span class="format-chip">${calc.mode === "pickpack" ? "PICK PACK" : "UNIDAD"}</span><span>${esc(calc.presentation)}</span><span>${state.orders} PEDIDOS</span></div></article>`;
}

function renderConsulta() {
  const items = state.filtered.slice(0, 500);
  $("consultaBody").innerHTML = items.map((item) => {
    const calc = calculate(item);
    const review = item.sapStatus !== "ok" || item.formatStatus !== "ok";
    const override = state.overrides[item.id] || "auto";
    return `<tr><td><input class="row-select" type="checkbox" data-id="${item.id}" ${state.selected.has(item.id) ? "checked" : ""}></td><td class="cell-title"><b>${esc(item.sap)}</b><small>${esc(item.name)}</small></td><td>${esc(item.category)}</td><td>${esc(item.code || "Pendiente")}</td><td>${formatNumber(item.usage, 1)}</td><td><b>${formatMinMax(calc.min, calc.mode)}</b></td><td><b>${formatMinMax(calc.max, calc.mode)}</b></td><td><select class="table-format" data-id="${item.id}"><option value="auto" ${override === "auto" ? "selected" : ""}>Base</option><option value="unidad" ${override === "unidad" ? "selected" : ""}>Unidad</option><option value="pickpack" ${override === "pickpack" ? "selected" : ""}>Pick Pack</option></select></td><td><span class="status-dot ${review ? "review" : ""}">${review ? "Revisar" : "Validado"}</span></td></tr>`;
  }).join("") || '<tr><td colspan="9" class="empty-state">Sin resultados.</td></tr>';
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
  if (event.target.classList.contains("table-format")) {
    if (event.target.value === "auto") delete state.overrides[id]; else state.overrides[id] = event.target.value;
    persistState();
  }
  renderAll();
}

function selectFiltered() {
  state.filtered.forEach((item) => state.selected.add(item.id));
  state.previewPage = Math.max(0, Math.ceil(state.selected.size / PAGE_SIZE) - 1);
  renderAll();
  toast(`${state.filtered.length} ingrediente(s) agregados a la exportación.`);
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
  return [...state.selected].map((id) => byId.get(id)).filter(Boolean);
}

function onPhotoChange(event) {
  const file = event.target.files?.[0];
  if (!file) return;
  const image = $("rackPhoto");
  image.onload = () => { $("photoStage").classList.add("has-photo"); renderMarkers(); };
  image.src = URL.createObjectURL(file);
}

function clearPhoto() {
  $("photoInput").value = "";
  $("rackPhoto").removeAttribute("src");
  $("photoStage").classList.remove("has-photo");
}

function renderMarkers() {
  if (!state.store) return;
  const items = selectedItemsCurrent();
  const positions = state.markerPositions[state.store.code] || (state.markerPositions[state.store.code] = {});
  $("markerCount").textContent = String(items.length);
  $("markerList").innerHTML = items.map((item, index) => `<div class="marker-row"><span class="marker-number">${index + 1}</span><span><b>${esc(item.name)}</b><small>${esc(item.sap)}</small></span></div>`).join("") || '<div class="empty-state">Selecciona etiquetas para crear marcadores.</div>';
  const layer = $("markerLayer");
  layer.innerHTML = "";
  items.forEach((item, index) => {
    const defaultPosition = { x: 6 + (index % 6) * 15, y: 8 + Math.floor(index / 6) * 14 };
    const position = positions[item.id] || defaultPosition;
    const marker = document.createElement("button");
    marker.type = "button";
    marker.className = "marker";
    marker.textContent = String(index + 1);
    marker.title = item.name;
    marker.style.left = `${position.x}%`;
    marker.style.top = `${position.y}%`;
    bindMarkerDrag(marker, item.id, positions);
    layer.appendChild(marker);
  });
}

function bindMarkerDrag(marker, ingredientId, positions) {
  let active = false;
  marker.addEventListener("pointerdown", (event) => { active = true; marker.classList.add("dragging"); marker.setPointerCapture(event.pointerId); });
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

function openExportConfirmation() {
  const items = selectedItemsCurrent();
  if (!items.length) { toast("Selecciona al menos un ingrediente antes de exportar."); return; }
  if (!window.jspdf?.jsPDF) { toast("El motor PDF local no está disponible."); return; }
  const pages = Math.ceil(items.length / PAGE_SIZE);
  $("confirmExportSummary").textContent = `${state.store.label} · Sem ${compactWeeks([...state.weeks])} · ${items.length} etiquetas · ${pages} hoja(s).`;
  $("confirmExportDialog").showModal();
}

function buildPdf(items) {
  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF({ unit: "mm", format: "letter", orientation: "landscape", compress: true, putOnlyUsedFonts: true });
  pdf.setProperties({ title: "Etiquetas MIN MAX", subject: `${state.store.label} · Semanas ${compactWeeks([...state.weeks])}`, creator: "Max & Min Remaster" });
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
    ["TIENDA", state.store.label],
    ["SEMANAS", compactWeeks([...state.weeks])],
    ["ACTUALIZACIÓN", formatDate(manifest.generated)],
  ];
  const widths = [width * .42, width * .25, width * .33];
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
  drawFittedLines(pdf, item.sap, x + 3, y + 2.2, width - 6, topH - 8.2, 10.4, 6.2, 2);
  const identity = `${item.name} | #DIA ${item.code || "—"} | #SAP ${item.woe || "—"}`;
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
  $("healthBadge").querySelector("span").textContent = `Datos hasta Sem ${manifest.weeks.at(-1)} · ${matched}/${total} SAP · ${counts.storesWithData} tiendas`;
}

async function fetchStoreData(path) {
  let lastError;
  for (let attempt = 1; attempt <= 2; attempt += 1) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);
    try {
      const separator = path.includes("?") ? "&" : "?";
      const response = await fetch(`${path}${separator}v=${encodeURIComponent(manifest.generated)}`, { cache: "no-store", signal: controller.signal });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => setTimeout(resolve, 350));
    } finally { clearTimeout(timeout); }
  }
  throw lastError;
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
