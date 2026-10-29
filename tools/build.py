"""Собирает исходники компендиума (JSON по документу на файл) из данных в tools/data.

Запуск из папки модуля:  python3 tools/build.py
Затем упаковка в LevelDB: npm run pack
"""

import copy
import hashlib
import html
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from data import abilities, bestiary, equipment, pregens, ships, specializations, tables, traits  # noqa: E402

MODULE_ID = "star-spindle-compendium"
SRC = ROOT / "src" / "packs"

SKILL_LABELS = {
    "melee": "Ближний бой", "strength": "Сила", "shooting": "Стрельба", "dexterity": "Проворство",
    "stealth": "Скрытность", "piloting": "Пилотирование", "observation": "Наблюдательность", "survival": "Выживание",
    "cybershamanism": "Кибершаманство", "mechanics": "Механика", "science": "Наука", "healing": "Знахарство",
    "influence": "Влияние", "leadership": "Лидерство", "culture": "Культура", "witchcraft": "Ведовство",
}

ICONS = {
    "weapon": "icons/svg/sword.svg", "armor": "icons/svg/shield.svg", "gear": "icons/svg/item-bag.svg",
    "implant": "icons/svg/pawprint.svg", "ability": "icons/svg/book.svg", "trait": "icons/svg/aura.svg",
    "specialization": "icons/svg/mystery-man.svg", "injury": "icons/svg/blood.svg",
    "shipWeapon": "icons/svg/explosion.svg", "shipModule": "icons/svg/circle.svg",
    "shipUpgrade": "icons/svg/upgrade.svg", "cargo": "icons/svg/chest.svg",
}

STATS = {"coreVersion": "13.345", "systemId": "star-spindle", "systemVersion": "0.3.0"}


def make_id(*parts):
    """Стабильный 16-символьный идентификатор документа."""
    return hashlib.sha1("/".join(map(str, parts)).encode()).hexdigest()[:16]


def p(text):
    """Текст в абзацы HTML."""
    if not text:
        return ""
    return "".join(f"<p>{html.escape(line)}</p>" for line in str(text).split("\n") if line.strip())


def ul(lines):
    return "<ul>" + "".join(f"<li>{html.escape(x)}</li>" for x in lines) + "</ul>"


class Pack:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self.folders = {}

    def folder(self, name, doc_type="Item", parent=None):
        key = (name, parent)
        if key not in self.folders:
            fid = make_id(self.name, "folder", name, parent or "")
            self.folders[key] = {
                "_id": fid, "_key": f"!folders!{fid}", "name": name, "type": doc_type,
                "folder": parent, "sorting": "a", "sort": len(self.folders) * 100000,
                "color": None, "description": "", "flags": {}
            }
        return self.folders[key]["_id"]

    def add(self, doc):
        self.docs.append(doc)
        return doc

    def write(self):
        out = SRC / self.name
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True)
        for doc in [*self.folders.values(), *self.docs]:
            slug = re.sub(r"[^\w]+", "_", doc["name"].lower()).strip("_")[:40]
            (out / f"{slug}_{doc['_id']}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def effect(owner_key, owner_id, name, img, changes, parent_kind="items"):
    eid = make_id(owner_id, "effect", name)
    return {
        "_id": eid, "_key": f"!{parent_kind}.effects!{owner_id}.{eid}",
        "name": name, "img": img, "type": "base", "system": {},
        "changes": [{"key": k, "mode": 2, "value": str(v), "priority": None} for k, v in changes],
        "disabled": False, "transfer": True, "duration": {}, "origin": None, "statuses": [],
        "description": "", "tint": "#ffffff", "sort": 0, "flags": {}
    }


def item(pack, name, type_, system, folder=None, effects=None, img=None, key=None):
    iid = make_id(pack.name, type_, key or name)
    doc = {
        "_id": iid, "_key": f"!items!{iid}", "name": name, "type": type_,
        "img": img or ICONS[type_], "system": system, "effects": [],
        "folder": folder, "sort": len(pack.docs) * 100, "ownership": {"default": 0}, "flags": {}, "_stats": STATS
    }
    for e in effects or []:
        doc["effects"].append(effect("items", iid, name, doc["img"], e))
    return pack.add(doc)


def bonus_fields(bonus):
    if not bonus:
        return {"modifier": 0, "bonusTarget": "", "conditional": False}
    mod, target, conditional = bonus
    return {"modifier": mod, "bonusTarget": "checks" if target == "checks" else f"skill.{target}", "conditional": conditional}


def physical(size="standard", price=0, quantity=1):
    return {"quantity": quantity, "size": size, "quality": 0, "price": price, "equipped": False, "stored": False}


# --------------------------------------------------------------------------
#  Специализации
# --------------------------------------------------------------------------

def build_specializations():
    pack = Pack("specializations")
    for s in specializations.SPECIALIZATIONS:
        gear = [f"{a} или {b}" for a, b in s["gear"]]
        desc = (p(s["description"])
                + f"<h3>Рекомендуемые навыки</h3>{p(', '.join(SKILL_LABELS[x] for x in s['skills']))}"
                + f"<h3>Модификатор репутации</h3>{p(('+' if s['reputation'] > 0 else '') + str(s['reputation']))}"
                + f"<h3>Дополнительный опыт</h3>{ul(s['xp'])}"
                + f"<h3>Примеры положительных черт</h3>{ul(s['positive'])}"
                + f"<h3>Примеры отрицательных черт</h3>{ul(s['negative'])}"
                + f"<h3>Стартовое снаряжение на выбор</h3>{ul(gear)}")
        item(pack, s["name"], "specialization", {
            "description": desc,
            "variations": s["variations"],
            "recommendedSkills": s["skills"],
            "reputationModifier": s["reputation"],
            "xpActions": "; ".join(s["xp"]),
            "traitExamples": "Положительные: " + ", ".join(s["positive"]) + ". Отрицательные: " + ", ".join(s["negative"]) + ".",
            "startingGear": "; ".join(gear),
        })
    return pack


# --------------------------------------------------------------------------
#  Особые способности
# --------------------------------------------------------------------------

def build_abilities():
    pack = Pack("abilities")
    for skill, entries in abilities.ABILITIES.items():
        folder = pack.folder(SKILL_LABELS[skill])
        for idx, entry in enumerate(entries):
            name, desc = entry[0], entry[1]
            bonus = entry[2] if len(entry) > 2 else None
            active = name.endswith("*")
            clean = name.rstrip(" *")
            tier = idx // 2 + 1
            pair = entries[idx ^ 1][0].rstrip(" *")
            text = p(desc) + p(f"Уровень {tier}. Выбирается вместо «{pair}».")
            if active:
                text += p("Активная способность: −1 Воля, Мастер получает жетон Чернобога, повторно — после длительного отдыха.")
            changes = abilities.EFFECTS.get(clean)
            item(pack, clean, "ability", {
                "description": text, "skill": skill, "tier": tier, "active": active, "used": False,
                **bonus_fields(bonus)
            }, folder=folder, effects=[changes] if changes else None, key=f"{skill}/{clean}")

    root = pack.folder("Ведовство")
    for branch, practices in abilities.WITCHCRAFT.items():
        folder = pack.folder(branch, parent=root)
        for tier, (name, desc) in enumerate(practices, start=1):
            text = (p(desc) + p(f"Ветка «{branch}», уровень ведовства {tier}. Нужна положительная черта «{branch}».")
                    + p("Практика ведовства: проверка ведовства, продолжительное действие, −1 Воля, Мастер получает жетон Чернобога, повторно — после длительного отдыха."))
            item(pack, name, "ability", {
                "description": text, "skill": "witchcraft", "tier": tier, "active": True, "used": False,
                **bonus_fields(None)
            }, folder=folder, key=f"witchcraft/{branch}/{name}")
    return pack


# --------------------------------------------------------------------------
#  Черты
# --------------------------------------------------------------------------

def build_traits():
    pack = Pack("traits")
    pos = pack.folder("Положительные черты")
    for entry in traits.POSITIVE:
        name, desc = entry[0], entry[1]
        bonus = entry[2] if len(entry) > 2 else None
        item(pack, name, "trait", {"description": p(desc), "kind": "positive", "craft": False, "level": 1, **bonus_fields(bonus)}, folder=pos)
    witch = pack.folder("Ветки ведовства")
    for name, desc in traits.WITCHCRAFT_BRANCHES.items():
        item(pack, name, "trait", {
            "description": p(desc) + p("Можно выбрать не более двух веток. Практики открываются по уровню навыка ведовства."),
            "kind": "positive", "craft": False, "level": 1, **bonus_fields(None)
        }, folder=witch)
    crafts = pack.folder("Ремёсла")
    for name, skills in traits.CRAFTS.items():
        item(pack, name, "trait", {
            "description": p(f"Ремесло. Нужный навык: {skills} (хотя бы 1).")
                           + p("Ремесло — положительная черта, улучшаемая до 5 уровня вместо получения новой черты. "
                               "Добыча: навык + характеристика + уровень ремесла; ресурс уровня N требует N успехов. "
                               "Производство: навык + характеристика + разница между уровнем ремесла и уровнем предмета."),
            "kind": "positive", "craft": True, "level": 1, **bonus_fields(None)
        }, folder=crafts)
    neg = pack.folder("Отрицательные черты")
    for name in traits.NEGATIVE:
        item(pack, name, "trait", {"description": "", "kind": "negative", "craft": False, "level": 1, **bonus_fields(None)}, folder=neg)
    return pack


# --------------------------------------------------------------------------
#  Оружие
# --------------------------------------------------------------------------

def size_from(props, default="standard"):
    low = props.lower()
    if "громоздк" in low:
        return "bulky"
    if "тяжёл" in low or "тяжел" in low:
        return "heavy"
    if "маленьк" in low:
        return "small"
    if "лёгк" in low or "легк" in low:
        return "light"
    return default


def describe_properties(props, glossary):
    lines = []
    low = props.lower()
    for key, text in glossary.items():
        if key.lower() in low:
            lines.append(f"<strong>{html.escape(key)}:</strong> {html.escape(text)}")
    return "".join(f"<p>{x}</p>" for x in lines)


def build_weapons():
    pack = Pack("weapons")
    melee = pack.folder("Оружие ближнего боя")
    for name, mod, init, dmg, crit, props, price in equipment.MELEE:
        system = {
            **physical(size_from(props), price), "skill": "melee", "modifier": mod, "initiative": init,
            "damage": dmg, "crit": crit, "range": "close" if "длинное" in props.lower() else "pointBlank",
            "armorPiercing": 2 if "бронебойн" in props.lower() else 0, "automatic": False,
            "properties": props, "ammo": {"value": 0, "max": 0},
            "description": describe_properties(props, equipment.MELEE_PROPERTIES)
        }
        item(pack, name, "weapon", system, folder=melee)

    ranged_root = pack.folder("Оружие дальнего боя")
    for category, name, mod, init, dmg, crit, rng, props, price in equipment.RANGED:
        folder = pack.folder(category, parent=ranged_root)
        system = {
            **physical(size_from(props), price), "skill": "shooting", "modifier": mod, "initiative": init,
            "damage": dmg, "crit": crit, "range": rng,
            "armorPiercing": 2 if "бронебойн" in props.lower() else 0,
            "automatic": "автоматическое" in props.lower(),
            "properties": props, "ammo": {"value": 0, "max": 0},
            "description": describe_properties(props, equipment.RANGED_PROPERTIES)
        }
        item(pack, name, "weapon", system, folder=folder)

    mods = pack.folder("Модификации и боеприпасы")
    for name, cost, desc in equipment.WEAPON_MODS:
        item(pack, name, "gear", {**physical("small"), **bonus_fields(None),
                                  "description": p(desc) + p(f"Стоимость: {cost} от цены оружия.")}, folder=mods)
    return pack


def build_armor():
    pack = Pack("armor")
    for category, name, defense, size, props, price in equipment.ARMOR:
        folder = pack.folder(category)
        item(pack, name, "armor", {
            **physical(size, price), "defense": defense, "properties": props,
            "description": describe_properties(props, equipment.ARMOR_PROPERTIES)
        }, folder=folder)
    upgrades = pack.folder("Улучшения брони")
    for key in ("Дополнительное защитное покрытие", "Гидростатический гель", "Датчик движения", "Встроенное оружие", "Встроенное оборудование"):
        text = {
            "Дополнительное защитное покрытие": "+1 к классу защиты.",
            "Гидростатический гель": equipment.ARMOR_PROPERTIES["Гидростатический гель"],
            "Датчик движения": equipment.ARMOR_PROPERTIES["Датчик движения"],
            "Встроенное оружие": "В броню встраивается лёгкое оружие, которое тяжело обнаружить без специальных приборов. Оружие оплачивается отдельно.",
            "Встроенное оборудование": "В броню встраивается лёгкий или маленький предмет снаряжения. Снаряжение оплачивается отдельно.",
        }[key]
        item(pack, f"{key} (улучшение брони)", "gear", {**physical("small"), **bonus_fields(None),
                                                        "description": p(text) + p("Стоимость установки: 100–150% от стартовой цены брони.")},
             folder=upgrades)
    return pack


def build_gear():
    pack = Pack("gear")
    for category, name, size, price, desc, bonus in equipment.GEAR:
        folder = pack.folder(category)
        item(pack, name, "gear", {**physical(size, price), **bonus_fields(bonus), "description": p(desc)}, folder=folder)
    expl = pack.folder("Взрывчатка")
    for category, name, power, dmg, crit, rng, props, price in equipment.EXPLOSIVES:
        folder = pack.folder(category, parent=expl)
        stats = f"Мощность: {power}. Урон: {dmg or '—'}. Крит.: {crit or '—'}. Дистанция: {rng}." + (f" {props}." if props else "")
        size = size_from(props, "light")
        item(pack, name, "gear", {**physical(size, price), **bonus_fields(None),
                                  "description": p(stats) + p(equipment.EXPLOSION_RULES)}, folder=folder)
    spells = pack.folder("Заговоры")
    for name, desc in equipment.SPELLS:
        item(pack, f"Заговор «{name}»", "gear", {**physical("small", 700), **bonus_fields(None),
                                                "description": p(desc) + p("Сила эффекта X равна количеству успехов при проверке кибершаманства. Цена заговора: 700–6000.")},
             folder=spells)
    return pack


def build_implants():
    pack = Pack("implants")
    folders = {"prosthesis": pack.folder("Протезы"), "cyber": pack.folder("Киберимпланты")}
    for name, kind, price, illegal, desc, bonus, changes in equipment.IMPLANTS:
        text = p(desc) + p("После установки к6 дней проверки, связанные с новой частью тела, получают −2.")
        if kind == "cyber":
            text += p("Каждый второй установленный киберимплант снижает максимальную волю на 1.")
        item(pack, name, "implant", {"description": text, "kind": kind, "illegal": illegal, "price": price, **bonus_fields(bonus)},
             folder=folders["cyber" if kind == "cyber" else "prosthesis"], effects=[changes] if changes else None)
    return pack


def build_injuries():
    pack = Pack("injuries")
    for code, name, lethal, deadline, effect_text, period, penalties, shock in tables.INJURIES:
        changes = [(f"system.skills.{skill}.bonus", value) for skill, value in penalties]
        desc = (p(effect_text)
                + p(f"Смерть: {lethal}. Крайний срок помощи: {deadline}. Период излечения: {period} дн.")
                + (p("Штрафы к проверкам уже учтены активным эффектом травмы.") if changes else ""))
        item(pack, name, "injury", {
            "description": desc, "code": str(code), "lethal": lethal != "Нет", "deadline": deadline,
            "effect": effect_text, "period": period, "strength": shock
        }, effects=[changes] if changes else None)
    return pack


# --------------------------------------------------------------------------
#  Корабли
# --------------------------------------------------------------------------

def build_ship_parts():
    pack = Pack("ship-parts")
    weapons_root = pack.folder("Корабельные орудия")
    for category, name, mod, dmg, crit, rng, dtype, ignore, loc, props, price in ships.WEAPONS:
        folder = pack.folder(category, parent=weapons_root)
        item(pack, name, "shipWeapon", {
            "description": p(props) if props else "", "modifier": mod, "damage": dmg, "crit": crit, "range": rng,
            "damageType": dtype, "ignoresArmor": ignore, "location": loc, "properties": props, "price": price,
            "ammo": {"value": 0, "max": 0}
        }, folder=folder)

    base = pack.folder("Обязательные модули")
    extra = pack.folder("Дополнительные модули")
    upgrades = pack.folder("Улучшения")
    for name, category, desc, ups in ships.MODULES:
        text = p(desc)
        if ups:
            text += "<h3>Улучшения</h3>" + ul([f"{u} ({pct}%): {d}" for u, pct, d in ups])
        item(pack, name, "shipModule", {"description": text, "category": category, "state": "normal", "upgrades": ""},
             folder=base if category == "base" else extra)
        for u, pct, d in ups:
            item(pack, u, "shipUpgrade", {"description": p(d) + p(f"Улучшение модуля «{name}». Стоимость: {pct}% от базовой цены корабля."),
                                          "costPercent": pct}, folder=upgrades)
    for name, pct, d in ships.UPGRADES:
        item(pack, name, "shipUpgrade", {"description": p(d) + p(f"Стоимость: {pct}% от базовой цены корабля."), "costPercent": pct}, folder=upgrades)
    return pack


CARGO_BY_CLASS = {1: 1, 2: 5, 3: 50, 4: 250, 5: 1000}
ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}


def embed(source, actor_id, override=None, salt=""):
    """Копия предмета из пака для вложения в актёра."""
    doc = copy.deepcopy(source)
    new_id = make_id(actor_id, doc["_id"], salt)
    doc["_id"] = new_id
    doc["_key"] = f"!actors.items!{actor_id}.{new_id}"
    doc.pop("folder", None)
    doc["flags"] = {"core": {"sourceId": f"Compendium.{MODULE_ID}.{source['_pack']}.Item.{source['_id']}"}} if "_pack" in source else {}
    doc.pop("_pack", None)
    for e in doc.get("effects", []):
        e["_key"] = f"!actors.items.effects!{actor_id}.{new_id}.{e['_id']}"
    if override:
        for k, v in override.items():
            ref = doc["system"]
            *path, last = k.split(".")
            for part in path:
                ref = ref[part]
            ref[last] = v
    return doc


def index(*packs):
    result = {}
    for pack in packs:
        for doc in pack.docs:
            d = copy.deepcopy(doc)
            d["_pack"] = pack.name
            result.setdefault((d["type"], d["name"]), d)
            result.setdefault(d["name"], d)
    return result


def prototype_token(name, img, link=True, disposition=1):
    return {
        "name": name, "actorLink": link, "disposition": disposition, "displayName": 20, "displayBars": 20,
        "bar1": {"attribute": "health"}, "bar2": {"attribute": "will"},
        "texture": {"src": img}, "width": 1, "height": 1, "sight": {"enabled": True}
    }


def actor_base(pack, name, type_, system, img, folder=None):
    aid = make_id(pack.name, type_, name)
    return {
        "_id": aid, "_key": f"!actors!{aid}", "name": name, "type": type_, "img": img, "system": system,
        "items": [], "effects": [], "folder": folder, "sort": len(pack.docs) * 100,
        "ownership": {"default": 0}, "flags": {}, "_stats": STATS,
        "prototypeToken": prototype_token(name, img, link=(type_ != "npc"), disposition=1 if type_ != "npc" else -1)
    }


def build_ships(parts):
    pack = Pack("ships")
    idx = index(parts)
    for (name, cls, hull, size, energy, dur, man, sig, armor, speed, fuel, slots, price, modules, upgrades) in ships.EXAMPLES:
        folder = pack.folder(f"{ROMAN[cls]} класс", doc_type="Actor")
        cargo_modules = sum(entry[1] for entry in modules if entry[0] == "Грузовой отсек")
        hull_desc = next((d for h, d in ships.HULLS if h == hull), "")
        system = {
            "shipClass": cls, "size": size, "hull": hull, "hullBonuses": hull_desc.split(". ")[0] + ".",
            "flaw": "", "baseCost": price, "lastMaintenance": "",
            "debt": {"initial": 0, "remaining": 0, "monthly": 0},
            "attributes": {k: {"value": v, "max": v} for k, v in {
                "durability": dur, "energy": energy, "maneuverability": man, "signature": sig,
                "armor": armor, "speed": speed, "fuel": fuel}.items()},
            "energyAllocation": {k: 0 for k in ("weapons", "engines", "repair", "sensors", "cyber")},
            "batteries": 0, "criticals": "", "cargoMax": CARGO_BY_CLASS[cls] * cargo_modules,
            "modulesMax": slots, "crew": [], "logbook": p(f"Пример корабля из книги правил. Цена: {price:,} сверкредитов.".replace(",", " "))
        }
        doc = actor_base(pack, name, "ship", system, "icons/svg/target.svg", folder)
        doc["prototypeToken"]["bar1"] = {"attribute": "attributes.durability"}
        doc["prototypeToken"]["bar2"] = {"attribute": "attributes.energy"}
        doc["prototypeToken"]["width"] = doc["prototypeToken"]["height"] = size
        for entry in modules:
            mname, count = entry[0], entry[1]
            for n in range(count):
                if mname.startswith("w:"):
                    src = idx[("shipWeapon", mname[2:])]
                    doc["items"].append(embed(src, doc["_id"], {"location": entry[2]}, salt=f"{entry[2]}{n}"))
                else:
                    src = idx[("shipModule", mname)]
                    doc["items"].append(embed(src, doc["_id"], {"category": src["system"]["category"]}, salt=n))
        for uname, count in upgrades:
            src = idx[("shipUpgrade", uname)]
            for n in range(count):
                doc["items"].append(embed(src, doc["_id"], salt=n))
        pack.add(doc)
    return pack


# --------------------------------------------------------------------------
#  Готовые персонажи
# --------------------------------------------------------------------------

SKILLS = list(SKILL_LABELS)


def build_pregens(*packs):
    pack = Pack("characters")
    idx = index(*packs)
    for pc in pregens.PREGENS:
        a = pc["attributes"]
        system = {
            "attributes": {k: {"value": v} for k, v in a.items()},
            "skills": {s: {"value": pc["skills"].get(s, 0), "bonus": 0} for s in SKILLS},
            "health": {"value": a["body"] + a["agility"], "max": a["body"] + a["agility"], "bonus": 0},
            "will": {"value": a["intellect"] + a["empathy"], "max": a["intellect"] + a["empathy"], "bonus": 0},
            "bonuses": {"checks": 0, "initiative": 0, "armor": 0}, "speed": 10,
            "biography": p(pc["bio"]), "injuries": "",
            "supercredits": pc["credits"], "reputation": pc["reputation"], "xp": 0,
            "origin": "", "religion": "", "blessing": 0, "heroTokens": 0, "encumbranceBonus": 0,
            "resources": {f"t{i}": 0 for i in range(1, 6)},
            "cabin": {"description": "", "storage": ""},
            "factions": {k: 0 for k in ("demos", "commune", "peddlers", "frontiers", "church", "outcasts")},
            "clans": {k: 0 for k in ("wolf", "eagle", "snake", "ram", "owl", "bear")},
            "appearance": "", "notes": p(f"Роль: {pc['role']}.")
        }
        doc = actor_base(pack, pc["name"], "character", system, "icons/svg/mystery-man.svg")
        aid = doc["_id"]

        def add(src, override=None, salt=""):
            doc["items"].append(embed(src, aid, override, salt))

        add(idx[("specialization", pc["specialization"])])
        add(idx[("trait", pc["positive"])])
        neg = idx.get(("trait", pc["negative"]))
        if neg:
            add(neg)
        else:
            add({"_id": make_id(aid, "neg"), "name": pc["negative"], "type": "trait", "img": ICONS["trait"],
                 "system": {"description": "", "kind": "negative", "craft": False, "level": 1, **bonus_fields(None)},
                 "effects": [], "sort": 0, "ownership": {"default": 0}, "flags": {}, "_stats": STATS})
        for n, entry in enumerate(pc["items"]):
            if isinstance(entry, dict):
                t = entry["type"]
                system_ = {**physical(entry.get("size", "standard")), **bonus_fields(None), "description": ""}
                if t == "armor":
                    system_ = {**physical(entry["size"]), "defense": entry["defense"], "properties": entry.get("properties", ""),
                               "description": "", "equipped": True}
                add({"_id": make_id(aid, "own", entry["name"]), "name": entry["name"], "type": t, "img": ICONS[t],
                     "system": system_, "effects": [], "sort": 0, "ownership": {"default": 0}, "flags": {}, "_stats": STATS})
                continue
            qty = 1
            if isinstance(entry, tuple):
                entry, qty = entry
            src = idx[entry]
            override = {"quantity": qty} if "quantity" in src["system"] else {}
            if src["type"] in ("weapon", "armor"):
                override["equipped"] = True
            add(src, override, salt=n)
        pack.add(doc)
    return pack


# --------------------------------------------------------------------------
#  Бестиарий
# --------------------------------------------------------------------------

RANGED_HINTS = ("плев", "смесь", "слюн", "сгусток", "огневик", "пистолет", "винтовк", "глаз", "зеркальц", "язык", "валун", "прялка")
PEACEFUL = {"Алая шапка", "Домовой", "Жар-птица", "Птица-говорун", "Горбунок", "Вилорог", "Звёздный кит", "Дра-кошка", "Гиперборейский жук"}


def creature_weapon(actor_id, w):
    name, mod, init, dmg, crit, rng, props = w
    ranged = rng in ("medium", "long", "extreme") or any(h in name.lower() for h in RANGED_HINTS)
    wid = make_id(actor_id, "weapon", name)
    return {
        "_id": wid, "_key": f"!actors.items!{actor_id}.{wid}", "name": name, "type": "weapon", "img": ICONS["weapon"],
        "system": {**physical("standard"), "equipped": True, "skill": "shooting" if ranged else "melee",
                   "modifier": mod, "initiative": init, "damage": dmg, "crit": crit, "range": rng,
                   "armorPiercing": 2 if "бронебойн" in props.lower() else 0, "automatic": "автоматическ" in props.lower(),
                   "properties": props, "ammo": {"value": 0, "max": 0}, "description": p(props) if props else ""},
        "effects": [], "sort": 0, "ownership": {"default": 0}, "flags": {}, "_stats": STATS
    }


def build_bestiary():
    pack = Pack("bestiary")
    for c in bestiary.BESTIARY:
        folder = pack.folder(c["cat"], doc_type="Actor")
        a = c["a"]
        text = p(c["desc"])
        if c["traits"]:
            text += "<h3>Черты</h3>" + "".join(
                f"<p><strong>{html.escape(n)}</strong>{f' ({html.escape(cost)})' if cost else ''}: {html.escape(d)}</p>" for n, cost, d in c["traits"])
        if c["sub"]:
            text += ("<h3>Подвиды</h3><table><tr><th>Подвид</th><th>Места обитания</th><th>Отличия</th></tr>"
                     + "".join(f"<tr><td>{html.escape(n)}</td><td>{html.escape(h)}</td><td>{html.escape(d)}</td></tr>" for n, h, d in c["sub"])
                     + "</table>")
        if c["cat"] == bestiary.SPACE:
            text += f"<h3>Правила боя с космической фауной</h3>{p(bestiary.SPACE_RULES)}"
        system = {
            "attributes": {k: {"value": a[k]} for k in ("body", "agility", "intellect", "empathy")},
            "skills": {s_: {"value": c["s"].get(s_, 0), "bonus": 0} for s_ in SKILLS},
            "health": {"value": c["hp"], "max": c["hp"], "bonus": 0},
            "will": {"value": c["will"], "max": c["will"], "bonus": 0},
            "bonuses": {"checks": 0, "initiative": 0, "armor": 0},
            "speed": c.get("speed", 10), "biography": text, "injuries": "",
            "role": c["cat"], "useFormula": False, "danger": c["danger"], "rarity": c["rarity"],
            "actionPoints": 3, "defenses": "; ".join(c["defenses"]), "notes": ""
        }
        doc = actor_base(pack, c["name"], "npc", system, "icons/svg/terror.svg", folder)
        doc["prototypeToken"]["actorLink"] = False
        doc["prototypeToken"]["disposition"] = 0 if c["name"] in PEACEFUL else -1
        aid = doc["_id"]
        for w in c["w"]:
            doc["items"].append(creature_weapon(aid, w))
        if c.get("armor"):
            aname, value = c["armor"]
            arid = make_id(aid, "armor", aname)
            doc["items"].append({
                "_id": arid, "_key": f"!actors.items!{aid}.{arid}", "name": aname, "type": "armor", "img": ICONS["armor"],
                "system": {**physical("light"), "equipped": True, "defense": value, "properties": "Естественная броня", "description": ""},
                "effects": [], "sort": 0, "ownership": {"default": 0}, "flags": {}, "_stats": STATS
            })
        for n, cost, d in c["traits"]:
            tid = make_id(aid, "trait", n)
            label = n + (f" ({cost})" if cost else "")
            doc["items"].append({
                "_id": tid, "_key": f"!actors.items!{aid}.{tid}", "name": label, "type": "trait", "img": ICONS["trait"],
                "system": {"description": p(d), "kind": "positive", "craft": False, "level": 1, **bonus_fields(None)},
                "effects": [], "sort": 0, "ownership": {"default": 0}, "flags": {}, "_stats": STATS
            })
        pack.add(doc)

    folder = pack.folder("Домашний скот и животные", doc_type="Actor")
    for name, hp, will in bestiary.LIVESTOCK:
        system = {
            "attributes": {k: {"value": 1} for k in ("body", "agility", "intellect", "empathy")},
            "skills": {s_: {"value": 0, "bonus": 0} for s_ in SKILLS},
            "health": {"value": hp, "max": hp, "bonus": 0}, "will": {"value": will, "max": will, "bonus": 0},
            "bonuses": {"checks": 0, "initiative": 0, "armor": 0}, "speed": 10,
            "biography": p("Сельскохозяйственное животное, завезённое на Аврору со времён падения «Гипербореи»."),
            "injuries": "", "role": "Домашний скот", "useFormula": False, "danger": 0, "rarity": 3,
            "actionPoints": 3, "defenses": "", "notes": ""
        }
        doc = actor_base(pack, name, "npc", system, "icons/svg/pawprint.svg", folder)
        doc["prototypeToken"]["actorLink"] = False
        doc["prototypeToken"]["disposition"] = 0
        pack.add(doc)
    return pack


# --------------------------------------------------------------------------
#  Таблицы
# --------------------------------------------------------------------------

def table(pack, name, formula, rows, description=""):
    tid = make_id(pack.name, "table", name)
    results = []
    for n, (rng, rname, text) in enumerate(rows):
        rid = make_id(tid, n)
        results.append({
            "_id": rid, "_key": f"!tables.results!{tid}.{rid}", "type": "text",
            "name": rname, "description": text, "text": f"<strong>{html.escape(rname)}</strong>: {text}" if rname else text,
            "img": "icons/svg/d20-black.svg", "range": list(rng), "weight": rng[1] - rng[0] + 1, "drawn": False, "flags": {}
        })
    return pack.add({
        "_id": tid, "_key": f"!tables!{tid}", "name": name, "img": "icons/svg/d20-grey.svg",
        "description": description, "formula": formula, "replacement": True, "displayRoll": True,
        "results": results, "folder": None, "sort": len(pack.docs) * 100, "ownership": {"default": 0}, "flags": {}, "_stats": STATS
    })


def build_tables(injuries):
    pack = Pack("tables")
    d66 = "(1d6 * 10) + 1d6"
    by_name = {d["name"]: d for d in injuries.docs}
    rows = []
    for code, name, lethal, deadline, eff, period, _, _ in tables.INJURIES:
        link = f"@UUID[Compendium.{MODULE_ID}.injuries.Item.{by_name[name]['_id']}]{{{name}}}"
        rows.append(((code, code), name, f"{html.escape(eff)}. Смерть: {lethal}; срок: {deadline}; период: {period}. {link}"))
    table(pack, "Таблица травм (к66)", d66, rows, "Первый к6 — десятки, второй — единицы.")
    table(pack, "Критические повреждения корабля (к66)", d66,
          [((c, c), n, f"{html.escape(e)}. Починка: {html.escape(f)}.") for c, n, e, f in tables.SHIP_CRITS])
    table(pack, "Случайный отсек (к66)", d66, [(r, n, "") for r, n in tables.COMPARTMENTS], tables.COMPARTMENT_NOTE)
    table(pack, "Неудачный прыжок (к66)", d66, [(r, "", html.escape(t)) for r, t in tables.JUMPS])
    table(pack, "Износ корабля (к6)", "1d6", [((n, n), s, html.escape(e)) for n, s, e in tables.WEAR])
    return pack


# --------------------------------------------------------------------------
#  Справочник
# --------------------------------------------------------------------------

def build_reference():
    pack = Pack("reference")
    jid = make_id("reference", "ships")
    pages = []

    def page(name, content):
        pid = make_id(jid, name)
        pages.append({"_id": pid, "_key": f"!journal.pages!{jid}.{pid}", "name": name, "type": "text",
                      "text": {"content": content, "format": 1}, "title": {"show": True, "level": 1},
                      "sort": len(pages) * 100, "ownership": {"default": -1}, "flags": {}})

    page("Базовые значения кораблей", p(ships.BASE_VALUES))
    page("Типы корпусов", "".join(f"<h3>{html.escape(n)}</h3>{p(d)}" for n, d in ships.HULLS))
    page("Изъяны кораблей", p("Изъян действует, только когда Мастер активирует его, потратив жетоны Чернобога.")
         + "".join(f"<h3>{html.escape(n)}</h3>{p(d)}" for n, d in ships.FLAWS))
    pack.add({"_id": jid, "_key": f"!journal!{jid}", "name": "Справочник: корабли", "pages": pages,
              "folder": None, "sort": 0, "ownership": {"default": 0}, "flags": {}, "_stats": STATS})
    return pack


def write_init_script(tables_pack):
    """Скрипт модуля: подключает таблицы к66 к настройкам системы, если они ещё не заданы."""
    ids = {d["name"]: d["_id"] for d in tables_pack.docs}
    mapping = {
        "injury": ids["Таблица травм (к66)"],
        "shipCrit": ids["Критические повреждения корабля (к66)"],
        "compartment": ids["Случайный отсек (к66)"],
        "jump": ids["Неудачный прыжок (к66)"],
    }
    lines = ",\n".join(f'  {k}: "Compendium.{MODULE_ID}.tables.RollTable.{v}"' for k, v in mapping.items())
    (ROOT / "scripts").mkdir(exist_ok=True)
    (ROOT / "scripts" / "init.mjs").write_text(
        "// Сгенерировано tools/build.py. Подключает таблицы к66 компендиума к настройкам системы.\n"
        f"const TABLES = {{\n{lines}\n}};\n\n"
        "Hooks.once(\"ready\", async () => {\n"
        "  if (!game.user.isGM || (game.system.id !== \"star-spindle\")) return;\n"
        "  for (const [key, uuid] of Object.entries(TABLES)) {\n"
        "    const setting = `table.${key}`;\n"
        "    if (!game.settings.get(\"star-spindle\", setting)) await game.settings.set(\"star-spindle\", setting, uuid);\n"
        "  }\n"
        "});\n", encoding="utf-8")


def main():
    if SRC.exists():
        shutil.rmtree(SRC)
    specs = build_specializations()
    abil = build_abilities()
    trts = build_traits()
    weap = build_weapons()
    arm = build_armor()
    gear = build_gear()
    impl = build_implants()
    inj = build_injuries()
    parts = build_ship_parts()
    shps = build_ships(parts)
    chars = build_pregens(specs, trts, weap, arm, gear, impl)
    tabs = build_tables(inj)
    ref = build_reference()
    best = build_bestiary()
    write_init_script(tabs)
    for pack in (specs, abil, trts, weap, arm, gear, impl, inj, parts, shps, chars, tabs, ref, best):
        pack.write()
        print(f"{pack.name:16} {len(pack.docs):4} документов, {len(pack.folders):3} папок")


if __name__ == "__main__":
    main()
