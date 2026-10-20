import { cp, mkdir, rm } from "node:fs/promises";
import { spawnSync } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const siteRoot = resolve(repositoryRoot, "site");
const outputRoot = resolve(repositoryRoot, "dist");

const check = spawnSync("python3", [resolve(repositoryRoot, "scripts/check_public_tree.py"), siteRoot], {
  cwd: repositoryRoot,
  encoding: "utf8",
  stdio: "inherit",
});
if (check.error) throw check.error;
if (check.status !== 0) process.exit(check.status ?? 1);

await rm(outputRoot, { recursive: true, force: true });
await mkdir(outputRoot, { recursive: true });
await cp(siteRoot, outputRoot, { recursive: true });
console.log("built static site in dist/");
