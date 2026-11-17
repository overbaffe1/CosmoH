const { chromium: p } = require("playwright-core"),
  c = require("@sparticuz/chromium"),
  axe = require("axe-core"),
  fs = require("fs"),
  path = require("path");
(async () => {
  fs.mkdirSync(path.join(__dirname, "../results"), { recursive: true });
  const b = await p.launch({
      executablePath: await c.executablePath(),
      args: c.args,
      headless: true,
    }),
    page = await b.newPage({ viewport: { width: 1440, height: 1080 } }),
    out = [];
  await page.goto(process.env.APP_ORIGIN || "http://127.0.0.1:8000/");
  await page.waitForFunction(
    () => !document.querySelector("#inputFields").disabled,
  );
  await page.locator("#calculate").click();
  await page.waitForFunction(
    () => document.querySelector("#resultState").textContent === "Рассчитано",
  );
  for (const theme of ["light", "dark"]) {
    if (theme === "dark") await page.locator("#themeToggle").click();
    await page.addScriptTag({ content: axe.source });
    const r = await page.evaluate(() =>
      axe.run(document, {
        runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
      }),
    );
    out.push({ theme, violations: r.violations });
  }
  fs.writeFileSync(
    path.join(__dirname, "../results/calculator-accessibility.json"),
    JSON.stringify(out, null, 2),
  );
  console.log(
    out.map((x) => ({
      theme: x.theme,
      violations: x.violations.map((v) => [
        v.id,
        v.impact,
        v.nodes.map((n) => n.target),
      ]),
    })),
  );
  await b.close();
  if (
    out.some((x) =>
      x.violations.some((v) => ["serious", "critical"].includes(v.impact)),
    )
  )
    throw Error("Calculator accessibility regression");
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
