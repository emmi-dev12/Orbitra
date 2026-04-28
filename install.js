#!/usr/bin/env node
/**
 * Post-install: ensure Python >=3.11 and install orbitra + playwright.
 */
const { execSync, spawnSync } = require("child_process");
const path = require("path");

function run(cmd, opts = {}) {
  const result = spawnSync(cmd, { shell: true, stdio: "inherit", ...opts });
  if (result.status !== 0) process.exit(result.status || 1);
}

function getPython() {
  for (const bin of ["python3.12", "python3.11", "python3", "python"]) {
    try {
      const out = execSync(`${bin} -c "import sys; print(sys.version_info[:2])"`, {
        stdio: ["ignore", "pipe", "ignore"],
      }).toString().trim();
      const match = out.match(/\((\d+),\s*(\d+)\)/);
      if (match) {
        const [, maj, min] = match.map(Number);
        if (maj > 3 || (maj === 3 && min >= 11)) return bin;
      }
    } catch {}
  }
  return null;
}

const py = getPython();
if (!py) {
  console.error(
    "\n[orbitra] ERROR: Python 3.11+ not found.\n" +
    "Install it from https://python.org/downloads or via:\n" +
    "  brew install python@3.12    # macOS\n" +
    "  sudo apt install python3.12 # Debian/Ubuntu\n"
  );
  process.exit(1);
}

console.log(`[orbitra] Using ${py}`);
console.log("[orbitra] Installing Python package from GitHub...");

// Install from GitHub (pip supports direct git URLs)
run(
  `${py} -m pip install --quiet --upgrade ` +
  `"orbitra @ git+https://github.com/emmi-dev12/Orbitra.git"`
);

console.log("[orbitra] Installing Playwright browsers (chromium)...");
run(`${py} -m playwright install chromium`);

console.log("\n[orbitra] Installation complete. Run: orbitra\n");
