#!/usr/bin/env node
/**
 * orbitra CLI shim — delegates to the Python package.
 */
const { spawnSync } = require("child_process");
const path = require("path");

function getPython() {
  for (const bin of ["python3.12", "python3.11", "python3", "python"]) {
    try {
      const { status } = spawnSync(bin, ["--version"], { stdio: "ignore" });
      if (status === 0) return bin;
    } catch {}
  }
  return "python3";
}

const args = process.argv.slice(2);
const result = spawnSync(getPython(), ["-m", "orbitra", ...args], {
  stdio: "inherit",
  env: process.env,
});

process.exit(result.status ?? 0);
