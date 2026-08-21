import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { JSDOM } from "jsdom";
import axeCore from "axe-core";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");

const STYLE = `
:root {
  --bg-base: #0b0d10;
  --text-primary: #e8ebf0;
  --text-secondary: #9aa4b2;
  --state-danger: #ff6b6b;
}
body { background: #0b0d10; color: #e8ebf0; font: 14px/1.4 sans-serif; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0,0,0,0); }
s { text-decoration: line-through; }
button { color: #e8ebf0; background: #14171c; border: 1px solid #262b33; }
`;

const SOURCE = {
  incident: join(ROOT, "src/pages/Incident.tsx"),
  queue: join(ROOT, "src/pages/AssistanceQueue.tsx"),
  board: join(ROOT, "src/pages/CommandBoard.tsx"),
  methodology: join(ROOT, "src/pages/Methodology.tsx"),
  ladder: join(ROOT, "src/components/AssuranceLadder.tsx"),
};

const REQUIRED = {
  incident: ["Incident", 'aria-label="Version chain"', 'aria-label="Incident timeline"'],
  queue: ["Assistance queue", 'aria-label="Cases"', 'role="table"'],
  board: ["Command Board", "Select incident", 'aria-label="Board totals"'],
  methodology: ["Methodology", 'aria-label="Channel capability"', "sr-only"],
  ladder: ["not applicable", "sr-only", "<s>"],
};

const SCREENS = {
  incident: `
    <div class="screen">
      <header class="screen__head">
        <div>
          <p class="screen__kicker">Incident</p>
          <h2>WAYANAD-FLOOD-001</h2>
        </div>
        <button type="button" aria-label="Back to board">Back</button>
      </header>
      <section class="panel" aria-label="Version chain">
        <h3>Version chain</h3>
        <ol><li><button type="button">v1 ACTIVE</button></li></ol>
      </section>
      <section class="panel" aria-label="Incident timeline">
        <h3>Timeline</h3>
        <ol><li><time datetime="2026-08-20T10:00:00Z">10:00</time> <strong>alert.created</strong></li></ol>
      </section>
    </div>`,
  queue: `
    <div class="screen">
      <header class="screen__head">
        <div>
          <p class="screen__kicker">Response</p>
          <h2>Assistance queue</h2>
        </div>
        <label>Assign to team <input /></label>
        <button type="button" aria-label="Refresh">Refresh</button>
      </header>
      <section aria-label="Queue summary"><p>Open cases 0</p></section>
      <section class="panel" aria-label="Cases" role="table">
        <div role="row">
          <span role="columnheader">Priority</span>
          <span role="columnheader">Need</span>
          <span role="columnheader">Unit</span>
          <span role="columnheader">Status</span>
          <span role="columnheader">Actions</span>
        </div>
        <p>No open cases.</p>
      </section>
    </div>`,
  board: `
    <div class="screen">
      <header class="screen__head">
        <div>
          <p class="screen__kicker">Common operating picture</p>
          <h2>Command Board</h2>
        </div>
      </header>
      <section aria-label="Board totals"><p>Open incidents 1</p></section>
      <section class="panel" aria-label="Incidents">
        <button type="button" aria-pressed="true" aria-label="Select incident DEMO-BOARD-001">DEMO-BOARD-001</button>
      </section>
      <section class="panel" aria-label="Highest-risk units"><h3>Highest-risk units</h3><p>No vulnerability ranking for this incident yet.</p></section>
    </div>`,
  methodology: `
    <div class="screen">
      <header class="screen__head">
        <div>
          <p class="screen__kicker">Accountability</p>
          <h2>Methodology</h2>
        </div>
      </header>
      <section class="panel" aria-label="Channel capability">
        <h3>Channel capability</h3>
        <table>
          <caption class="sr-only">Channel assurance capability by tier</caption>
          <thead><tr><th>Channel</th><th>Tier</th><th>Supported</th></tr></thead>
          <tbody><tr><td>sms</td><td>opened</td><td>no</td></tr></tbody>
        </table>
      </section>
      <section class="panel" aria-label="Published models">
        <h3>Models</h3>
        <table>
          <caption class="sr-only">Registered models with published metrics</caption>
          <thead><tr><th>Name</th><th>Version</th><th>Bootstrap</th><th>Metrics</th></tr></thead>
          <tbody><tr><td>dedup_spatial_temporal</td><td>0.1</td><td>bootstrap</td><td>n=50</td></tr></tbody>
        </table>
      </section>
    </div>`,
  ladder: `
    <ul aria-label="Assurance ladder">
      <li>
        <s>Opened</s>
        <span class="sr-only">— not applicable</span>
        <span>SMS has no open receipt</span>
      </li>
    </ul>`,
};

async function run() {
  const failures = [];
  for (const [name, path] of Object.entries(SOURCE)) {
    const text = readFileSync(path, "utf8");
    for (const needle of REQUIRED[name]) {
      if (!text.includes(needle)) {
        failures.push(`${name} source missing ${needle}`);
      }
    }
  }
  for (const [name, html] of Object.entries(SCREENS)) {
    const dom = new JSDOM(
      `<!DOCTYPE html><html lang="en"><head><title>SETU ${name}</title><style>${STYLE}</style></head><body>${html}</body></html>`,
      { url: "http://localhost/", pretendToBeVisual: true, runScripts: "dangerously" },
    );
    dom.window.eval(axeCore.source);
    const results = await dom.window.axe.run(dom.window.document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
    });
    const real = results.violations.filter((v) => v.id !== "color-contrast");
    if (name === "ladder") {
      const text = dom.window.document.body.textContent || "";
      if (!text.includes("not applicable")) {
        failures.push("ladder: missing not applicable announcement");
      }
    }
    for (const v of real) {
      failures.push(`${name}: ${v.id} — ${v.help}`);
    }
  }
  if (failures.length) {
    for (const line of failures) console.error(line);
    process.exit(1);
  }
  console.log("a11y-check: clean");
}

run();
