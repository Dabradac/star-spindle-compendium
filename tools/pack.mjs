// Упаковка исходников src/packs/* в LevelDB-паки packs/* (и обратно с --unpack).
import { compilePack, extractPack } from "@foundryvtt/foundryvtt-cli";
import { readdir, rm } from "node:fs/promises";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..");
const src = path.join(root, "src", "packs");
const dest = path.join(root, "packs");
const unpack = process.argv.includes("--unpack");

for (const name of await readdir(unpack ? dest : src)) {
  const from = path.join(unpack ? dest : src, name);
  const to = path.join(unpack ? src : dest, name);
  if (unpack) await extractPack(from, to, { clean: true });
  else {
    await rm(to, { recursive: true, force: true });
    await compilePack(from, to, { recursive: false });
  }
  console.log(`${unpack ? "Распакован" : "Собран"} пак ${name}`);
}
