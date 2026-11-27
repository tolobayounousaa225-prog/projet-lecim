// Tests de navigateur de la PSIE : démarre l'application sur une base jetable, déroule les parcours clés
// (dépôt de demande, connexion par rôle, recherche, espace faîtière, notifications), contrôle l'accessibilité (axe)
// et l'absence de débordement sur mobile. Sortie non nulle au moindre échec.
//
// Usage : cd psie/e2e && npm install && npx playwright install chromium && node run.js
const { chromium } = require("playwright");
const { spawn, spawnSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const PORT = process.env.E2E_PORT || "8931";
const BASE = `http://127.0.0.1:${PORT}`;
const PASSWORD = "Motdepasse-Test-1";
const BACKEND = path.resolve(__dirname, "..", "backend");
const PYTHON = process.env.PYTHON || "python";
const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "psie-e2e-"));
const env = { ...process.env, DATABASE_URL: `sqlite:///${path.join(tmp, "e2e.db")}`, TWO_FACTOR_ENABLED: "false", SCHEDULER_ENABLED: "false",
  COOKIE_SECURE: "false", PUBLIC_BASE_URL: BASE, SECRET_KEY: "e2e-secret-key-e2e-secret-key-e2e-secret-key" };

let axeSource = "";
try { axeSource = fs.readFileSync(require.resolve("axe-core/axe.min.js"), "utf8"); } catch (e) { console.log("axe-core indisponible : contrôle d'accessibilité ignoré"); }

const failures = [];
const check = (ok, message) => { console.log(`${ok ? "✓" : "✗"} ${message}`); if (!ok) failures.push(message); };

async function waitForServer() {
  for (let i = 0; i < 60; i++) {
    try { const r = await fetch(`${BASE}/health`); if (r.ok) return; } catch (e) { /* pas encore prêt */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  throw new Error("l'application ne démarre pas");
}

async function login(browser, email, space = "/login", lang = "fr", width = 1280) {
  const ctx = await browser.newContext({ viewport: { width, height: 860 } });
  await ctx.addCookies([{ name: "lang", value: lang, url: BASE }]);
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  await page.goto(BASE + space);
  await page.fill("input[name=email]", email);
  await page.fill("input[name=password]", PASSWORD);
  await page.click("button.btn");
  await page.waitForLoadState("networkidle");
  return { ctx, page, errors };
}

async function axeViolations(page) {
  if (!axeSource) return [];
  await page.evaluate(axeSource);
  const res = await page.evaluate(() => axe.run(document, { runOnly: ["wcag2a", "wcag2aa"] }));
  return res.violations.map((v) => `${v.id} (${(v.nodes[0] && v.nodes[0].target.join(" ")) || ""})`);
}

(async () => {
  let server;
  try {
    const seed = spawnSync(PYTHON, [path.join(__dirname, "seed.py")], { env, cwd: BACKEND, encoding: "utf8" });
    if (seed.status !== 0) throw new Error("amorçage de la base impossible : " + seed.stderr);
    server = spawn(PYTHON, ["-m", "uvicorn", "app.main:app", "--port", PORT], { env, cwd: BACKEND, stdio: "ignore" });
    await waitForServer();
    const browser = await chromium.launch();

    // 1. Visiteur : dépôt de demande, page épurée, suivi par code
    {
      const ctx = await browser.newContext(); const page = await ctx.newPage();
      await page.goto(`${BASE}/adhesion`);
      check((await page.locator(".topbar").count()) === 0, "dépôt de demande : aucun faux menu de site");
      await page.fill("input[name=nom]", "Union Test"); await page.fill("input[name=sigle]", "UTEST");
      await page.fill("input[name=representant_nom]", "Moussa Traoré"); await page.fill("input[name=email]", "contact@test.ci");
      await page.fill("input[name=telephone]", "+225 07 00 00 00 00");
      await page.check("input[name=accepte_statuts]"); await page.check("input[name=accepte_cotisations]");
      await page.click("form[action='/adhesion'] button.btn");
      await page.waitForLoadState("networkidle");
      const code = (await page.locator(".code").innerText()).trim();
      check(/^ADH-/.test(code), `demande envoyée, code de suivi reçu (${code})`);
      await page.goto(`${BASE}/adhesion/suivi`); await page.fill("input[name=code]", code); await page.click("form button.btn");
      check((await page.content()).includes("badge"), "suivi par code : l'état de la demande s'affiche");
      await ctx.close();
    }

    // 2. DEN : voit la demande, notification, recherche, filtre instantané
    {
      const { ctx, page, errors } = await login(browser, "den@psie.ci");
      await page.goto(`${BASE}/adhesions`);
      check((await page.content()).includes("UTEST"), "DEN : la nouvelle demande est dans la liste");
      check((await page.locator(".bell-count").count()) === 1, "DEN : la cloche signale la nouvelle demande");
      await page.goto(`${BASE}/faitieres`);
      const before = await page.locator("tbody tr:visible").count();
      await page.fill(".table-filter input", "hikma");
      const after = await page.locator("tbody tr:visible").count();
      check(before >= 7 && after === 1, `filtre instantané des membres (${before} → ${after})`);
      await page.goto(`${BASE}/recherche?q=nour`);
      check((await page.content()).includes("École NOUR"), "recherche globale : l'école trouvée");
      await page.goto(`${BASE}/statistiques`);
      check((await page.locator("figure.chart svg").count()) >= 3, "statistiques : graphiques affichés");
      check(errors.length === 0, "DEN : aucune erreur JavaScript ni de politique de sécurité" + (errors.length ? " — " + errors[0] : ""));
      await ctx.close();
    }

    // 2 bis. Supervision : le DEN consulte l'espace du secrétaire aux finances en lecture seule ; l'administrateur règle les accès en un clic
    {
      const { ctx, page, errors } = await login(browser, "den@psie.ci");
      await page.goto(`${BASE}/supervision`);
      await page.click("tr:has-text('fin@psie.ci') button:has-text('Voir son espace')");
      await page.goto(`${BASE}/cotisations`);
      check((await page.locator(".view-banner").count()) === 1, "supervision : bandeau « lecture seule » dans l'espace consulté");
      const write = await page.evaluate(async () => (await fetch("/cotisations/bareme", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "annee=2027&montant=1" })).status);
      check(write === 403, "supervision : aucune modification possible pendant la consultation");
      await page.click(".view-banner button");
      check((await page.locator(".view-banner").count()) === 0, "supervision : retour à son propre espace");
      check(errors.filter((e) => !/403/.test(e)).length === 0, "supervision : aucune erreur JavaScript");
      await ctx.close();
      const adm = await login(browser, "admin@psie.ci");
      await adm.page.goto(`${BASE}/acces`);
      await adm.page.click("button[data-preset='1'][data-role='communication']");
      check(/\d+ modification/.test(await adm.page.locator("#pending-count").innerText()), "accès par rubrique : profil « lecture » appliqué en un clic, modifications comptées");
      await adm.ctx.close();
    }

    // 3. Faîtière : ajoute une école, voit ses statistiques et reçoit l'annonce
    {
      const den = await login(browser, "den@psie.ci");
      await den.page.goto(`${BASE}/annonces`);
      await den.page.fill("input[name=titre]", "Assemblée annuelle"); await den.page.fill("textarea[name=texte]", "Rendez-vous en décembre.");
      await den.page.click("form[action='/annonces'] button.btn"); await den.ctx.close();
      const { ctx, page, errors } = await login(browser, "rep@psie.ci", "/login/faitiere");
      check((await page.locator(".bell-count").count()) === 1, "faîtière : la cloche signale l'annonce");
      await page.click("a:has-text('Écoles')");
      await page.fill("form[action$='/ecoles'] input[name=nom]", "École Nouvelle"); await page.click("form[action$='/ecoles'] button.btn");
      check((await page.content()).includes("École Nouvelle"), "faîtière : école ajoutée");
      await page.click("a:has-text('Statistiques')");
      check((await page.locator("figure.chart").count()) >= 1, "faîtière : ses statistiques avec graphiques");
      check(errors.length === 0, "faîtière : aucune erreur JavaScript" + (errors.length ? " — " + errors[0] : ""));
      const other = await page.goto(`${BASE}/faitieres/2/statistiques`);        // la faîtière n°2 n'est pas la sienne
      check(other.status() === 404 && !(await page.content()).includes("Organisation IQRA"), "faîtière : jamais les chiffres d'une autre faîtière");
      await ctx.close();
    }

    // 4. Contrôle d'accessibilité et de mise en page sur les pages principales, ordinateur et mobile, français et arabe
    const roles = [["den@psie.ci", "/login"], ["admin@psie.ci", "/login"], ["fin@psie.ci", "/login"], ["com@psie.ci", "/login"], ["rep@psie.ci", "/login/faitiere"]];
    let pages = 0; const problems = new Set();
    for (const [email, space] of roles) {
      for (const lang of ["fr", "ar"]) {
        const { ctx, page } = await login(browser, email, space, lang);
        const links = await page.$$eval("aside nav a[href^='/']", (as) => [...new Set(as.map((a) => a.getAttribute("href")))]);
        for (const href of links) {
          for (const [label, w] of [["ordinateur", 1280], ["mobile", 390]]) {
            await page.setViewportSize({ width: w, height: 800 });
            const r = await page.goto(BASE + href);
            if (!r || r.status() >= 400) { problems.add(`${email} ${href} → ${r && r.status()}`); continue; }
            pages++;
            const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
            if (over > 2) problems.add(`débordement ${over}px : ${email} ${href} (${label}/${lang})`);
            // Mise en page : un bloc décoré (carte, formulaire) affiché « en ligne » se casse sur plusieurs lignes
            const broken = await page.evaluate(() => {
              const out = [];
              document.querySelectorAll("main form, main section, main article, main div").forEach((e) => {
                const cs = getComputedStyle(e);
                const decorated = parseFloat(cs.borderTopWidth) > 0 || cs.boxShadow !== "none";
                if (cs.display === "inline" && decorated && e.querySelector("label, input, select, table, p, h2")) out.push(e.tagName.toLowerCase() + "." + String(e.className).split(" ")[0]);
              });
              return out;
            });
            for (const b of broken) problems.add(`mise en page (bloc décoré « en ligne ») ${b} : ${email} ${href} (${label}/${lang})`);
            if (w === 1280) for (const v of await axeViolations(page)) problems.add(`axe ${v} : ${email} ${href} (${lang})`);
          }
        }
        await ctx.close();
      }
    }
    check(problems.size === 0, `${pages} pages parcourues (5 rôles, FR/AR, ordinateur/mobile) : aucune erreur, aucun débordement, aucune violation d'accessibilité`);
    [...problems].slice(0, 20).forEach((p) => console.log("   - " + p));
    await browser.close();
  } catch (e) {
    check(false, "exécution interrompue : " + e.message);
  } finally {
    if (server) server.kill();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  console.log(failures.length ? `\n${failures.length} échec(s)` : "\nTous les parcours passent.");
  process.exit(failures.length ? 1 : 0);
})();
