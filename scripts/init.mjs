// Сгенерировано tools/build.py. Подключает таблицы к66 и к6 компендиума к настройкам системы.
const TABLES = {
  injury: "Compendium.star-spindle-compendium.tables.RollTable.aff0464ac2e15be9",
  shipCrit: "Compendium.star-spindle-compendium.tables.RollTable.d1fd193943387780",
  compartment: "Compendium.star-spindle-compendium.tables.RollTable.46bfb2d3e06a50c3",
  jump: "Compendium.star-spindle-compendium.tables.RollTable.e2ec4ab88e2e4655",
  wear: "Compendium.star-spindle-compendium.tables.RollTable.f0b1c0e8b9790f8b",
  vehicleCrit: "Compendium.star-spindle-compendium.tables.RollTable.05492337d16fc876"
};

Hooks.once("ready", async () => {
  if (!game.user.isGM || (game.system.id !== "star-spindle")) return;
  for (const [key, uuid] of Object.entries(TABLES)) {
    const setting = `table.${key}`;
    if (!game.settings.settings.has(`star-spindle.${setting}`)) continue;
    if (!game.settings.get("star-spindle", setting)) await game.settings.set("star-spindle", setting, uuid);
  }
});
