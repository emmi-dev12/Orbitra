#!/usr/bin/env node
/**
 * Post-install: create a dedicated venv at ~/.orbitra/venv and install orbitra.
 * Works with uv-managed, brew-managed, or system Python environments.
 */
const { execSync, spawnSync } = require("child_process");
const os = require("os");
const path = require("path");
const fs = require("fs");

const VENV_DIR = path.join(os.homedir(), ".orbitra", "venv");

function run(cmd, opts = {}) {
  const result = spawnSync(cmd, { shell: true, stdio: "inherit", ...opts });
  if (result.status !== 0) process.exit(result.status || 1);
}

function exec(cmd) {
  try {
    return execSync(cmd, { stdio: ["ignore", "pipe", "ignore"] }).toString().trim();
  } catch {
    return null;
  }
}

// ── 1. Find Python 3.11+ ─────────────────────────────────────────────────────
function getPython() {
  // Try uv's managed pythons first (avoids externally-managed-environment error)
  const uvPy = exec("uv python find 3.12") || exec("uv python find 3.11");
  if (uvPy) return uvPy;

  for (const bin of ["python3.12", "python3.11", "python3", "python"]) {
    const out = exec(`${bin} -c "import sys; print(sys.version_info[:2])"`);
    if (!out) continue;
    const match = out.match(/\((\d+),\s*(\d+)\)/);
    if (match) {
      const maj = Number(match[1]), min = Number(match[2]);
      if (maj > 3 || (maj === 3 && min >= 11)) return bin;
    }
  }
  return null;
}

const py = getPython();
if (!py) {
  console.error(
    "\n[orbitra] ERROR: Python 3.11+ not found.\n" +
    "Install via:  uv python install 3.12\n" +
    "         or:  brew install python@3.12\n"
  );
  process.exit(1);
}
console.log(`[orbitra] Python: ${py}`);

// ── 2. Create venv (skip if already exists) ──────────────────────────────────
const venvPy = path.join(VENV_DIR, "bin", "python");
const venvPyWin = path.join(VENV_DIR, "Scripts", "python.exe");
const venvPyBin = fs.existsSync(venvPyWin) ? venvPyWin : venvPy;

if (!fs.existsSync(venvPyBin)) {
  console.log(`[orbitra] Creating venv at ${VENV_DIR} ...`);
  fs.mkdirSync(path.dirname(VENV_DIR), { recursive: true });

  // Prefer uv venv (much faster), fall back to python -m venv
  const uvOk = exec("uv --version");
  if (uvOk) {
    run(`uv venv "${VENV_DIR}" --python "${py}" --quiet`);
  } else {
    run(`"${py}" -m venv "${VENV_DIR}"`);
  }
} else {
  console.log(`[orbitra] Reusing existing venv at ${VENV_DIR}`);
}

// ── 3. Install orbitra into the venv ─────────────────────────────────────────
console.log("[orbitra] Installing Python dependencies...");
const uvOk = exec("uv --version");
if (uvOk) {
  // uv pip is fast and respects the venv
  run(`uv pip install --quiet --python "${venvPyBin}" ` +
      `"git+https://github.com/emmi-dev12/Orbitra.git"`);
} else {
  run(`"${venvPyBin}" -m pip install --quiet --upgrade ` +
      `"git+https://github.com/emmi-dev12/Orbitra.git"`);
}

// ── 4. Install Playwright chromium into the venv ─────────────────────────────
console.log("[orbitra] Installing Playwright browsers (chromium)...");
run(`"${venvPyBin}" -m playwright install chromium`);

// ── 5. Write the venv path so the CLI shim can find it ───────────────────────
const stateFile = path.join(os.homedir(), ".orbitra", "venv_path");
fs.writeFileSync(stateFile, VENV_DIR, "utf8");

console.log("\n[orbitra] Done. Run: orbitra\n");
