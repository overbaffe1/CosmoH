"use strict";
const $ = (id) => document.getElementById(id),
  copy = (x) => JSON.parse(JSON.stringify(x));
const fmt = (x, d = 2) =>
  x == null
    ? "—"
    : Number(x).toLocaleString("ru-RU", { maximumFractionDigits: d });
const esc = (x) =>
  String(x ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
let control,
  plan,
  orders = {},
  demand = [],
  factors = {},
  revision = 0,
  last = null,
  pinned = null,
  busy = false;
const investmentNames = {
  EARTH_NEW: "Новый земной канал",
  LUNAR_ISRU: "Производство на Луне",
  ZBO: "Модернизация хранения",
};
const ruleNames = {
  RESERVE_45D: "Недостаточный резерв",
  BASE_TOTAL_SERVICE: "Не выполнен общий сервис",
  BASE_CRITICAL_SERVICE: "Не выполнен критический сервис",
  STORAGE_OVERFLOW: "Переполнение хранилища",
  STRESS_LOSS_LIMIT: "Превышены допустимые потери",
};
async function api(url, body) {
  const r = await fetch(
    url,
    body
      ? {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        }
      : {},
  );
  if (!r.ok) {
    let e;
    try {
      e = await r.json();
    } catch (_) {
      throw Error("Сервер недоступен: " + r.status);
    }
    throw Error(
      typeof e.detail === "string" ? e.detail : JSON.stringify(e.detail),
    );
  }
  return r.json();
}
function message(text, error = false) {
  $("message").textContent = text;
  $("message").classList.toggle("error", error);
}
function download(blob, name) {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function table(headers, rows) {
  return (
    "<table><thead><tr>" +
    headers.map((h) => '<th scope="col">' + esc(h) + "</th>").join("") +
    "</tr></thead><tbody>" +
    rows
      .map(
        (row) =>
          "<tr>" + row.map((v) => "<td>" + v + "</td>").join("") + "</tr>",
      )
      .join("") +
    "</tbody></table>"
  );
}
function numberInput(id, value, label, attrs = "") {
  return `<input id="${id}" type="number" value="${esc(value)}" aria-label="${esc(label)}" required ${attrs.includes("step=") ? "" : 'step="any"'} ${attrs}>`;
}
function dirty() {
  revision++;
  $("exportResult").disabled = true;
  $("pinResult").disabled = true;
  document.querySelector(".result-panel").classList.add("stale");
  $("resultState").textContent = last
    ? "Изменено · нужен пересчёт"
    : "Готово к расчёту";
  $("detailState").textContent = last
    ? "Ниже предыдущий расчёт, не новые значения"
    : "";
  message("Условия изменены. Нажмите «Рассчитать мой план».");
}
function setupOrders() {
  orders = {};
  for (const d of control.demand)
    for (const s of control.supply_sources) {
      const o = plan.decisions.supply_orders.find(
          (r) => r.year === d.year && r.source_id === s.source_id,
        ),
        r = plan.decisions.capacity_reservations.find(
          (r) => r.year === d.year && r.source_id === s.source_id,
        );
      orders[d.year + "-" + s.source_id] = {
        enabled: !!(o || r),
        ordered: o?.ordered_volume_t ?? 0,
        reserved: r?.reserved_capacity_t ?? 0,
        start: o?.start_day ?? 1,
        end: o?.end_day ?? 365,
        orderday: o?.order_day ?? (d.year - 2035) * 365 - 730,
        resStart: r?.start_day ?? 1,
        resEnd: r?.end_day ?? 365,
      };
    }
}
function renderOrders() {
  const y = +$("contractYear").value;
  const fields = [
    ["ordered", "Заказ, т", 'min="0"'],
    ["reserved", "Мощность, т/год", 'min="0"'],
    ["start", "Начало поставок", 'min="1" max="365" step="1"'],
    ["end", "Конец поставок", 'min="1" max="365" step="1"'],
    ["orderday", "Дата заказа", 'step="1"'],
    ["resStart", "Договор с дня", 'min="1" max="365" step="1"'],
    ["resEnd", "Договор по день", 'min="1" max="365" step="1"'],
  ];
  $("orderInputs").innerHTML = table(
    ["Источник", ...fields.map((f) => f[1])],
    control.supply_sources.map((s) => {
      const key = y + "-" + s.source_id,
        o = orders[key];
      return [
        `<div class="source-cell"><label><input type="checkbox" id="use-${s.source_id}" ${o.enabled ? "checked" : ""}>${esc(s.name)}</label><small>${fmt(s.variable_cost_mln_per_t)} млн/т · до ${fmt(s.capacity_t_per_year)} т/год</small></div>`,
        ...fields.map(([k, label, attrs]) =>
          numberInput(
            "order-" + s.source_id + "-" + k,
            o[k],
            s.name + " " + label,
            attrs + (o.enabled ? "" : " disabled"),
          ),
        ),
      ];
    }),
  );
  for (const s of control.supply_sources) {
    const o = orders[y + "-" + s.source_id];
    $("use-" + s.source_id).onchange = (e) => {
      o.enabled = e.target.checked;
      renderOrders();
      dirty();
    };
    for (const [k] of fields)
      $("order-" + s.source_id + "-" + k).oninput = (e) => {
        o[k] = e.target.value === "" ? null : Number(e.target.value);
        dirty();
      };
  }
}
function renderConditions() {
  $("demandInputs").innerHTML = table(
    ["Год", "Общий спрос", "Из него критический"],
    demand.map((r) => [
      r.year,
      numberInput(
        "demand-" + r.year,
        r.base_total_t,
        "Общий спрос " + r.year,
        'min="0"',
      ),
      numberInput(
        "critical-" + r.year,
        r.base_critical_t,
        "Критический спрос " + r.year,
        'min="0"',
      ),
    ]),
  );
  demand.forEach((r) => {
    for (const [prefix, key] of [
      ["demand", "base_total_t"],
      ["critical", "base_critical_t"],
    ])
      $(prefix + "-" + r.year).oninput = (e) => {
        r[key] = e.target.value === "" ? null : Number(e.target.value);
        dirty();
      };
  });
  $("shockInputs").innerHTML = table(
    ["Источник", "Множитель цены", "Исполнение заказа, %"],
    control.supply_sources.map((s) => [
      esc(s.name),
      numberInput(
        "price-" + s.source_id,
        factors[s.source_id].price,
        s.name + " множитель цены",
        'min="0"',
      ),
      numberInput(
        "delivery-" + s.source_id,
        factors[s.source_id].delivery,
        s.name + " исполнение",
        'min="0" max="100"',
      ),
    ]),
  );
  control.supply_sources.forEach((s) => {
    for (const key of ["price", "delivery"])
      $(key + "-" + s.source_id).oninput = (e) => {
        factors[s.source_id][key] =
          e.target.value === "" ? null : Number(e.target.value);
        dirty();
      };
  });
  customVisibility();
}
function customVisibility() {
  const own = $("environment").value === "CUSTOM";
  $("customConditions").hidden = !own;
  $("customConditions")
    .querySelectorAll("input,select")
    .forEach((e) => (e.disabled = !own));
  $("environmentHelp").textContent = own
    ? "TEAM_ASSUMPTION: отдельный опыт. Не накладывается поверх обязательного стресса."
    : "CASE_INPUT: условия организатора. Меняется среда, но не ваши заказы и инвестиции.";
}
function renderInvestments() {
  $("investmentInputs").innerHTML = control.investment_options
    .map((o) => {
      const d = plan.decisions.investments.find(
          (r) => r.investment_id === o.investment_id,
        ),
        id = o.investment_id;
      return `<div class="investment"><div><label class="name"><input id="invest-${id}" type="checkbox" ${d ? "checked" : ""}>${esc(investmentNames[id] || o.name)}</label><small>${fmt(o.total_capex_mln)} млн CAPEX · ${fmt(o.fixed_opex_mln_per_year)} млн/год OPEX</small></div><label>День оплаты${numberInput("decision-" + id, d?.decision_day ?? 0, "День оплаты " + id, 'min="0" step="1"' + (d ? "" : " disabled"))}</label><label>День ввода${numberInput("commission-" + id, d?.commission_day ?? 0, "День ввода " + id, 'min="0" step="1"' + (d ? "" : " disabled"))}</label></div>`;
    })
    .join("");
  for (const o of control.investment_options) {
    const id = o.investment_id;
    $("invest-" + id).onchange = () => {
      $("decision-" + id).disabled = $("commission-" + id).disabled = !$(
        "invest-" + id,
      ).checked;
      dirty();
    };
    for (const prefix of ["decision", "commission"])
      $(prefix + "-" + id).oninput = dirty;
  }
}
function synchronizePlan() {
  const p = copy(plan);
  p.plan_id = "TEAM_CALCULATOR";
  p.decisions.inventory_policy.opening_stock_t = +$("openingStock").value;
  p.assumptions.discount_rate.value = +$("discountRate").value / 100;
  p.assumptions.discount_rate.basis = "Ставка пользователя в лаборатории";
  p.decisions.supply_orders = [];
  p.decisions.capacity_reservations = [];
  for (const row of control.demand)
    for (const s of control.supply_sources) {
      const o = orders[row.year + "-" + s.source_id];
      if (!o.enabled) continue;
      for (const [key, v] of Object.entries(o))
        if (key !== "enabled" && (v === null || !Number.isFinite(v)))
          throw Error("Заполните договор " + s.name + " за " + row.year);
      p.decisions.supply_orders.push({
        source_id: s.source_id,
        year: row.year,
        ordered_volume_t: o.ordered,
        start_day: o.start,
        end_day: o.end,
        order_day: o.orderday,
      });
      p.decisions.capacity_reservations.push({
        source_id: s.source_id,
        year: row.year,
        reserved_capacity_t: o.reserved,
        start_day: o.resStart,
        end_day: o.resEnd,
      });
    }
  p.decisions.investments = control.investment_options
    .filter((o) => $("invest-" + o.investment_id).checked)
    .map((o) => ({
      investment_id: o.investment_id,
      decision_day: +$("decision-" + o.investment_id).value,
      commission_day: +$("commission-" + o.investment_id).value,
    }));
  return p;
}
function request() {
  if (!$("calculator").reportValidity())
    throw Error("Заполните выделенные поля.");
  const req = {
    plan: synchronizePlan(),
    scenario_id:
      $("environment").value === "CUSTOM" ? "BASE" : $("environment").value,
  };
  if ($("environment").value === "CUSTOM") {
    const basis = $("basis").value.trim();
    if (!basis) throw Error("Укажите основание собственных условий.");
    for (const r of demand)
      if (r.base_critical_t > r.base_total_t)
        throw Error("В " + r.year + " критический спрос больше общего.");
    const years =
      $("shockYear").value === "all"
        ? control.demand.map((r) => r.year)
        : [+$("shockYear").value];
    const scenario = {
      scenario_id: "TEAM_CALCULATOR_CUSTOM",
      status: "TEAM_ASSUMPTION",
      variable_price_multiplier: {},
      actual_delivery_share: {},
      notes: [
        basis,
        "Значения исследовательские, вероятность события не задаётся.",
      ],
    };
    for (const s of control.supply_sources) {
      scenario.variable_price_multiplier[s.name] = Object.fromEntries(
        years.map((y) => [y, factors[s.source_id].price]),
      );
      scenario.actual_delivery_share[s.name] = Object.fromEntries(
        years.map((y) => [y, factors[s.source_id].delivery / 100]),
      );
    }
    req.research_scenario = scenario;
    if (JSON.stringify(demand) !== JSON.stringify(control.demand))
      req.research_case_patch = { basis, demand: copy(demand) };
  }
  return req;
}
function plot(rows, series) {
  const max =
      Math.max(1, ...rows.flatMap((r) => series.map((s) => r[s[0]]))) * 1.1,
    x = (i) => 44 + (i * 540) / Math.max(1, rows.length - 1),
    y = (v) => 186 - (v / max) * 156;
  let svg =
    '<svg viewBox="0 0 610 230" role="img" aria-label="' +
    esc(series.map((s) => s[2]).join(", ")) +
    '">';
  for (let i = 0; i < 4; i++) {
    const v = (max * i) / 3;
    svg += `<line x1="44" x2="586" y1="${y(v)}" y2="${y(v)}"/><text x="2" y="${y(v) + 4}" font-size="10">${fmt(v, 0)}</text>`;
  }
  for (const [key, color, label] of series)
    svg += `<polyline fill="none" stroke="${color}" stroke-width="2" points="${rows.map((r, i) => x(i) + "," + y(r[key])).join(" ")}"><title>${esc(label)}</title></polyline>`;
  [...new Set(rows.map((r) => r.year))].forEach((year) => {
    const i = rows.findIndex((r) => r.year === year);
    svg += `<text x="${x(i)}" y="206" font-size="10" text-anchor="middle">${year}</text>`;
  });
  return (
    svg +
    '</svg><p class="hint">' +
    series.map((s) => esc(s[2])).join(" · ") +
    "</p>"
  );
}
function renderResult(r, req) {
  const s = r.summary;
  $("resultEmpty").hidden = true;
  $("resultContent").hidden = false;
  $("resultDetails").hidden = false;
  document.querySelector(".result-panel").classList.remove("stale");
  $("resultState").textContent = "Рассчитано";
  $("detailState").textContent = "Данные текущего расчёта";
  $("resultMetrics").innerHTML = [
    ["Полные расходы", s.total_cost_mln, "млн у.е."],
    [
      "Приведённые расходы",
      s.discounted_cost_mln,
      "млн · ставка " + fmt(s.discount_rate * 100) + "%",
    ],
    ["Не хватило топлива", s.shortage_t, "тонн"],
    ["Нарушения", s.violations, "по всем годам"],
  ]
    .map(
      ([label, n, unit], i) =>
        `<div class="metric"><small>${label}</small><strong class="${i > 1 && n > 0 ? "bad" : ""}">${fmt(n)}</strong><div class="unit">${unit}</div></div>`,
    )
    .join("");
  $("conclusion").textContent = s.violations
    ? `План не проходит ${s.violations} проверок. ${s.shortage_t > 1e-8 ? "Часть спроса не обеспечена." : "Дефицита нет, но этого недостаточно."} Причины и годы — в таблице ниже.`
    : "В выбранных условиях план проходит проверки. Это результат модели, а не гарантия реальных поставок.";
  $("resultBasis").textContent =
    (req.research_scenario
      ? "Собственные условия · TEAM_ASSUMPTION"
      : "Условия организатора · " + req.scenario_id) +
    ` · минимальный общий сервис ${fmt(s.min_total_service * 100)}%, критический ${fmt(s.min_critical_service * 100)}%.`;
  if (pinned) {
    $("previousComparison").hidden = false;
    const p = pinned.result.summary,
      sign = (x) => (x > 0 ? "+" : "");
    $("previousComparison").textContent =
      `К зафиксированному расчёту: расходы ${sign(s.total_cost_mln - p.total_cost_mln)}${fmt(s.total_cost_mln - p.total_cost_mln)} млн; дефицит ${sign(s.shortage_t - p.shortage_t)}${fmt(s.shortage_t - p.shortage_t)} т. Сравнение ваших двух запусков, не оценка оптимальности.`;
  }
  $("balanceTable").innerHTML = table(
    [
      "Год",
      "Спрос, т",
      "Поставка, т",
      "Потери, т",
      "Выдано, т",
      "Остаток, т",
      "Дефицит, т",
    ],
    r.yearly_balance.map((a) => [
      a.year,
      ...[
        "demand_t",
        "delivered_t",
        "losses_t",
        "served_t",
        "closing_inventory_t",
        "shortage_t",
      ].map((k) => fmt(a[k])),
    ]),
  );
  const bad = r.constraint_checks.filter((c) => !c.passed);
  $("checksTable").innerHTML = bad.length
    ? table(
        ["Правило", "Период", "Факт", "Нужно"],
        bad.map((c) => [
          esc(ruleNames[c.rule_id] || c.rule_id),
          esc(c.period),
          fmt(c.actual),
          esc(c.operator) + " " + fmt(c.limit) + " " + esc(c.unit),
        ]),
      )
    : '<p class="good">Все проверки выбранного плана пройдены.</p>';
  $("costTable").innerHTML = table(
    ["Год", "Закупка", "Договоры", "Хранение", "OPEX", "CAPEX", "Всего"],
    r.financial_breakdown.map((c) => [
      c.year,
      ...[
        "procurement_mln",
        "reservation_mln",
        "holding_mln",
        "fixed_opex_mln",
        "capex_mln",
        "total_mln",
      ].map((k) => fmt(c[k])),
    ]),
  );
  $("demandPlot").innerHTML = plot(r.yearly_balance, [
    ["demand_t", "#5682be", "Спрос, т"],
    ["served_t", "#20956b", "Выдано, т"],
  ]);
  const trace = r.inventory_trace.filter(
    (x, i) => i % 7 === 0 || x.day === 365,
  );
  $("stockPlot").innerHTML = plot(trace, [
    ["inventory_t", "#20956b", "Запас, т"],
    ["reserve_threshold_t", "#bd8237", "Резерв на начало года, т"],
  ]);
  $("exportResult").disabled = false;
  $("pinResult").disabled = false;
}
$("calculator").onsubmit = async (e) => {
  e.preventDefault();
  if (busy || !plan) return;
  let req;
  try {
    req = request();
  } catch (e) {
    message(e.message, true);
    return;
  }
  busy = true;
  const token = revision;
  $("calculate").disabled = true;
  message("Считаем ваш план по дням…");
  try {
    const r = await api("/api/run", req);
    if (token !== revision) {
      message("Условия изменились во время расчёта. Запустите ещё раз.");
      return;
    }
    last = { request: copy(req), result: r, revision: token };
    renderResult(r, req);
    message("Готово. Рассчитаны именно выбранные вами условия.");
    if (innerWidth < 850)
      document
        .querySelector(".result-panel")
        .scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    message("Ошибка: " + e.message, true);
  } finally {
    busy = false;
    $("calculate").disabled = false;
  }
};
$("exportResult").onclick = async () => {
  if (!last || last.revision !== revision) return;
  const saved = last;
  $("exportResult").disabled = true;
  try {
    const r = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(saved.request),
    });
    if (!r.ok) throw Error("Экспорт: HTTP " + r.status);
    download(await r.blob(), "cosmokontur-calculation.zip");
  } catch (e) {
    message(e.message, true);
  } finally {
    $("exportResult").disabled = !last || last.revision !== revision;
  }
};
$("pinResult").onclick = () => {
  if (last?.revision === revision) {
    pinned = copy(last);
    $("previousComparison").hidden = false;
    $("previousComparison").textContent =
      "Расчёт зафиксирован. Измените условия и запустите снова — покажем разницу.";
  }
};
$("saveProject").onclick = () => {
  try {
    const req = request();
    const doc = {
      format: "fuel-calculator-v1",
      case_version: control.version,
      request: req,
      settings: {
        environment: $("environment").value,
        shockYear: $("shockYear").value,
        basis: $("basis").value,
        demand: copy(demand),
        factors: copy(factors),
      },
    };
    download(
      new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" }),
      "cosmokontur-project.json",
    );
  } catch (e) {
    message(e.message, true);
  }
};
$("openProject").onclick = () => $("projectFile").click();
$("projectFile").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  try {
    if (file.size > 5 * 1024 * 1024) throw Error("Файл проекта больше 5 МБ");
    const d = JSON.parse(await file.text());
    if (d.format !== "fuel-calculator-v1" || d.case_version !== control.version)
      throw Error(
        "Нужен проект этого калькулятора с тем же контрольным набором. Другие форматы открываются в расширенном редакторе.",
      );
    if (
      !Number.isFinite(d.request?.plan?.assumptions?.discount_rate?.value) ||
      typeof d.settings?.basis !== "string" ||
      !d.settings.basis.trim()
    )
      throw Error("Неполный проект калькулятора");
    if (
      Object.keys(d.request.research_case_patch || {}).some(
        (k) => !["basis", "demand"].includes(k),
      )
    )
      throw Error(
        "Расширенные входные данные откройте в расширенном редакторе",
      );
    if (
      Object.keys(d.request.research_scenario || {}).some(
        (k) =>
          ![
            "scenario_id",
            "status",
            "variable_price_multiplier",
            "actual_delivery_share",
            "notes",
          ].includes(k),
      )
    )
      throw Error("Расширенный сценарий откройте в расширенном редакторе");
    await api("/api/run", d.request); // Validate the saved payload before changing the active form.
    if (
      !["BASE", "MANDATORY_STRESS", "CUSTOM"].includes(
        d.settings.environment,
      ) ||
      !["all", ...control.demand.map((r) => String(r.year))].includes(
        d.settings.shockYear,
      )
    )
      throw Error("Неизвестные настройки проекта");
    if (
      JSON.stringify(d.settings.demand.map((x) => x.year)) !==
      JSON.stringify(control.demand.map((x) => x.year))
    )
      throw Error("Неполный список лет");
    for (const s of control.supply_sources)
      if (
        !Number.isFinite(d.settings.factors[s.source_id]?.price) ||
        !Number.isFinite(d.settings.factors[s.source_id]?.delivery)
      )
        throw Error("Некорректные параметры источника");
    for (const r of d.settings.demand)
      if (
        !Number.isFinite(r.base_total_t) ||
        !Number.isFinite(r.base_critical_t) ||
        r.base_critical_t < 0 ||
        r.base_total_t < r.base_critical_t
      )
        throw Error("Неверный спрос в проекте");
    for (const v of Object.values(d.settings.factors))
      if (v.price < 0 || v.delivery < 0 || v.delivery > 100)
        throw Error("Неверные множители в проекте");
    plan = copy(d.request.plan);
    demand = copy(d.settings.demand);
    factors = copy(d.settings.factors);
    setupOrders();
    $("environment").value = d.settings.environment;
    $("shockYear").value = d.settings.shockYear;
    $("basis").value = d.settings.basis;
    $("openingStock").value = plan.decisions.inventory_policy.opening_stock_t;
    $("discountRate").value = plan.assumptions.discount_rate.value * 100;
    renderOrders();
    renderConditions();
    renderInvestments();
    dirty();
    message("Проект открыт. Нажмите «Рассчитать мой план» для нового запуска.");
  } catch (err) {
    message("Не удалось открыть: " + err.message, true);
  } finally {
    e.target.value = "";
  }
};
async function loadPlan() {
  const p = await api("/api/plans/" + $("preset").value);
  plan = p;
  demand = copy(control.demand);
  factors = Object.fromEntries(
    control.supply_sources.map((s) => [
      s.source_id,
      { price: 1, delivery: 100 },
    ]),
  );
  setupOrders();
  $("openingStock").value = p.decisions.inventory_policy.opening_stock_t;
  $("discountRate").value = p.assumptions.discount_rate.value * 100;
  $("environment").value = p.scenario_id;
  $("shockYear").value = "all";
  renderOrders();
  renderConditions();
  renderInvestments();
  dirty();
}
$("loadPlan").onclick = async () => {
  if (!control) return;
  if (
    !confirm(
      "Загрузить основу? Текущие значения будут заменены. Сохранённый проект останется у вас.",
    )
  )
    return;
  try {
    await loadPlan();
  } catch (e) {
    message(e.message, true);
  }
};
$("environment").onchange = () => {
  customVisibility();
  dirty();
};
$("contractYear").onchange = renderOrders;
for (const id of ["openingStock", "discountRate", "basis", "shockYear"])
  $(id).addEventListener("input", dirty);
(async () => {
  try {
    control = (await api("/api/case")).case;
    $("contractYear").innerHTML = control.demand
      .map((r) => `<option>${r.year}</option>`)
      .join("");
    $("contractYear").value = "2038";
    $("shockYear").innerHTML += $("contractYear").innerHTML;
    await loadPlan();
    $("inputFields").disabled = false;
    customVisibility();
    message("Основа загружена. Выберите условия и рассчитайте свой план.");
  } catch (e) {
    message("Не удалось загрузить данные: " + e.message, true);
  }
})();
