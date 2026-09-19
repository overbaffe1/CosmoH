const { chromium: pw } = require("playwright-core"),
  chromium = require("@sparticuz/chromium"),
  fs = require("fs"),
  path = require("path");
(async () => {
  const root = path.resolve(__dirname, "..");
  fs.mkdirSync(path.join(root, "results"), { recursive: true });
  const browser = await pw.launch({
      executablePath: await chromium.executablePath(),
      args: chromium.args,
      headless: true,
    }),
    page = await browser.newPage({
      viewport: { width: 1440, height: 1080 },
      acceptDownloads: true,
    });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const base = process.env.APP_ORIGIN || "http://127.0.0.1:8000";
  const check = (ok, msg) => {
    if (!ok) throw Error(msg);
  };
  async function run() {
    const p = page.waitForResponse(
      (r) => r.url().endsWith("/api/run") && r.request().method() === "POST",
    );
    await page.locator("#calculate").click();
    const res = await p;
    check(res.ok(), "Calculation failed: " + (await res.text()));
    await page.waitForFunction(
      () => document.querySelector("#resultState").textContent === "Рассчитано",
    );
    return res.json();
  }
  await page.goto(base);
  await page.waitForFunction(
    () => !document.querySelector("#inputFields").disabled,
  );
  check(
    await page.locator("#resultEmpty").isVisible(),
    "Must not pretend that a fresh form is already calculated",
  );
  const initial = await run();
  check(
    Math.abs(initial.summary.total_cost_mln - 10829.678567071034) < 1e-6,
    "Initial baseline changed",
  );
  await page.locator("#pinResult").click();
  await page.locator("#openingStock").fill("30");
  check(
    await page.locator("#exportResult").isDisabled(),
    "Stale export enabled",
  );
  const stock = await run();
  check(
    stock.input_plan.decisions.inventory_policy.opening_stock_t === 30,
    "Stock not applied",
  );
  check(
    stock.summary.total_cost_mln !== initial.summary.total_cost_mln,
    "Edited stock did not affect costs",
  );
  await page.locator("#openingStock").fill("20");
  await page.locator("#discountRate").fill("5");
  const rate = await run();
  check(
    rate.summary.discount_rate === 0.05 &&
      rate.summary.discounted_cost_mln < rate.summary.total_cost_mln,
    "Rate ignored",
  );
  const ordered = Number(await page.locator("#order-A-ordered").inputValue());
  await page.locator("#order-A-ordered").fill(String(ordered + 10));
  await page.locator("#contractYear").selectOption("2039");
  await page.locator("#contractYear").selectOption("2038");
  check(
    Number(await page.locator("#order-A-ordered").inputValue()) ===
      ordered + 10,
    "Switching years lost edited order",
  );
  const order = await run();
  check(
    order.input_plan.decisions.supply_orders.find(
      (x) => x.source_id === "A" && x.year === 2038,
    ).ordered_volume_t ===
      ordered + 10,
    "Order not in core request",
  );
  await page.locator("#environment").selectOption("CUSTOM");
  await page.locator("#shockYear").selectOption("2038");
  await page.locator("#delivery-D").fill("50");
  await page.locator("#price-A").fill("1.2");
  await page.locator("#demand-2038").fill("260");
  const custom = await run();
  check(
    custom.input_case.demand.find((r) => r.year === 2038).base_total_t === 260,
    "Custom demand ignored",
  );
  check(
    custom.provenance.scenario_definition.actual_delivery_share["Lunar-ISRU"][
      "2038"
    ] === 0.5,
    "Supply share ignored",
  );
  await page.locator("#invest-ZBO").uncheck();
  const noZbo = await run();
  check(
    !noZbo.input_plan.decisions.investments.some(
      (i) => i.investment_id === "ZBO",
    ),
    "Investment checkbox ignored",
  );
  await page.locator("#invest-ZBO").check();
  await run();
  let download = page.waitForEvent("download");
  await page.locator("#saveProject").click();
  const file = path.join(root, "results/calculator-project.json");
  await (await download).saveAs(file);
  await page.locator("#openingStock").fill("60");
  await page.locator("#projectFile").setInputFiles(file);
  await page.waitForFunction(() =>
    document.querySelector("#message").textContent.startsWith("Проект открыт"),
  );
  const reopened = await run();
  check(
    JSON.stringify(reopened.summary) === JSON.stringify(custom.summary),
    "Roundtrip changed results",
  );
  const unsupported = JSON.parse(fs.readFileSync(file, "utf8"));
  unsupported.request.research_case_patch.supply_sources = [];
  await page
    .locator("#projectFile")
    .setInputFiles({
      name: "unsupported.json",
      mimeType: "application/json",
      buffer: Buffer.from(JSON.stringify(unsupported)),
    });
  await page.waitForFunction(() =>
    document
      .querySelector("#message")
      .textContent.includes("Расширенные входные данные"),
  );
  check(
    Number(await page.locator("#openingStock").inputValue()) === 20 &&
      !(await page.locator("#exportResult").isDisabled()),
    "Rejected import changed the active calculation",
  );
  download = page.waitForEvent("download");
  await page.locator("#exportResult").click();
  await (
    await download
  ).saveAs(path.join(root, "results/calculator-result.zip"));
  await page.locator("#critical-2038").fill("999");
  await page.locator("#calculate").click();
  check(
    (await page.locator("#message").textContent()).includes(
      "критический спрос больше общего",
    ),
    "Friendly invalid-input error missing",
  );
  check(
    await page.locator("#exportResult").isDisabled(),
    "Invalid edit kept export live",
  );
  await page
    .locator("#critical-2038")
    .fill(
      String(
        custom.input_case.demand.find((r) => r.year === 2038).base_critical_t,
      ),
    );
  await page.locator("#environment").selectOption("MANDATORY_STRESS");
  const stress = await run();
  check(
    stress.scenario_id === "MANDATORY_STRESS" &&
      !stress.input_case.research_provenance,
    "Custom patch leaked into official stress",
  );
  // A late response must never be applied to newer inputs.
  await page.route("**/api/run", async (route) => {
    await new Promise((r) => setTimeout(r, 250));
    await route.continue();
  });
  await page.locator("#calculate").click();
  await page.locator("#openingStock").fill("31");
  await page.waitForFunction(
    () => !document.querySelector("#calculate").disabled,
  );
  check(
    (await page.locator("#message").textContent()).includes(
      "изменились во время",
    ),
    "Outdated async result applied",
  );
  await page.unroute("**/api/run");
  // Actual calculator screenshot, with a fresh baseline and its controls.
  page.on("dialog", (d) => d.accept());
  await page.locator("#loadPlan").click();
  await page.waitForFunction(
    () => document.querySelector("#openingStock").value === "20",
  );
  await run();
  await page.evaluate(() => scrollTo({ top: 0, behavior: "instant" }));
  const box = await page.locator(".workspace").boundingBox();
  await page.screenshot({
    path: path.join(root, "docs/assets/calculator.png"),
    clip: {
      x: box.x,
      y: box.y,
      width: box.width,
      height: Math.min(640, 1080 - box.y),
    },
  });
  await page.locator('header a[href="/evidence"]').click();
  await page.waitForURL("**/evidence");
  check(
    (await page.locator("h1").textContent()).includes("проверяемому"),
    "Evidence did not open in same tab",
  );
  check(
    (await page.request.get(base + "/evidence/")).ok(),
    "Evidence trailing slash failed",
  );
  await page.goto(base);
  await page.waitForFunction(
    () => !document.querySelector("#inputFields").disabled,
  );
  await page.setViewportSize({ width: 390, height: 844 });
  check(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
    "Mobile overflow",
  );
  await page.locator("#themeToggle").click();
  check(
    (await page.locator("html").getAttribute("data-theme")) === "dark",
    "Dark theme failed",
  );
  await page.screenshot({
    path: path.join(root, "results/calculator-mobile.png"),
    fullPage: true,
  });
  await browser.close();
  check(!errors.length, errors.join("\n"));
  console.log(
    "PASS calculator: editable stock/rate/contracts/demand/prices/delivery/investments, core results, stale response/export, JSON roundtrip, ZIP, errors, evidence navigation, mobile/themes",
  );
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
