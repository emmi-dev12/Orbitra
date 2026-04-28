#!/usr/bin/env node
/**
 * orbitra CLI shim — runs from the dedicated venv at ~/.orbitra/venv.
 */
const { spawnSync } = require("child_process");
const os = require("os");
const path = require("path");
const fs = require("fs");

function getVenvPython() {
  // Read venv location written by install.js
  const stateFile = path.join(os.homedir(), ".orbitra", "venv_path");
  if (fs.existsSync(stateFile)) {
    const venvDir = fs.readFileSync(stateFile, "utf8").trim();
    for (const rel of ["bin/python", "Scripts/python.exe"]) {
      const p = path.join(venvDir, rel);
      if (fs.existsSync(p)) return p;
    }
  }
  // Fallback: default venv location
  const fallback = path.join(os.homedir(), ".orbitra", "venv", "bin", "python");
  if (fs.existsSync(fallback)) return fallback;
  return "python3";
}

const args = process.argv.slice(2);
const result = spawnSync(getVenvPython(), ["-m", "orbitra", ...args], {
  stdio: "inherit",
  env: process.env,
});
process.exit(result.status ?? 0);
