#!/usr/bin/env python3
"""Vytvorí/aktualizuje dashboard "Meteostanica" v Home Assistante."""
import json, subprocess, sys

E = "meteostanica_vonku_1"
S, B, SW, NU, BT = "sensor." + E, "binary_sensor." + E, "switch." + E, "number." + E, "button." + E

def tile(entity, cols=6, **kw):
    c = {"type": "tile", "entity": entity, "grid_options": {"columns": cols}}
    c.update(kw); return c

def head(text, icon=None, style="title", **kw):
    c = {"type": "heading", "heading": text, "heading_style": style}
    if icon: c["icon"] = icon
    c.update(kw); return c

TREND = [{"type": "trend-graph", "hours_to_show": 24}]

def press(entity, icon, label, confirm=None):
    act = {"action": "perform-action", "perform_action": "button.press",
           "target": {"entity_id": entity}}
    if confirm: act["confirmation"] = {"text": confirm}
    return tile(entity, 6, icon=icon, name=label, tap_action=act)

# ---------------------------------------------------------------- PREHĽAD
uvod = {
    "title": "Prehľad", "path": "prehlad", "type": "sections",
    "icon": "mdi:weather-partly-cloudy", "max_columns": 3,
    "badges": [
        {"type": "entity", "entity": f"{B}_status_stanice", "show_name": True},
        {"type": "entity", "entity": f"{S}_uroven_baterie", "show_name": True},
        {"type": "entity", "entity": f"{S}_rezim_stanice", "show_name": False},
        {"type": "entity", "entity": f"{S}_vonkajsia_teplota", "show_name": True,
         "state_content": ["state", "last_changed"]},
    ],
    "header": {
        "layout": "responsive", "badges_position": "top",
        "card": {
            "type": "markdown", "text_only": True,
            "content": (
                "{% set f = states('" + S + "_predpoved_pocasia') %}"
                "{% set o = states('" + S + "_odporucanie_oblecenia') %}"
                "{% if f not in ['unknown','unavailable'] %}## {{ f }}\n"
                "{% endif %}"
                "{% if o not in ['unknown','unavailable'] %}{{ o }}"
                "{% else %}_Stanica spí alebo je offline — údaje sú z posledného prebudenia._"
                "{% endif %}"
            ),
        },
    },
    "sections": [
        {"type": "grid", "cards": [
            head("Práve teraz", "mdi:thermometer"),
            tile(f"{S}_vonkajsia_teplota", 12, features=TREND, features_position="inline"),
            tile(f"{S}_pocitova_teplota"),
            tile(f"{S}_rosny_bod"),
            tile(f"{S}_vonkajsia_vlhkost", 12, features=TREND, features_position="inline"),
            tile(f"{S}_tlak_hladina_mora", 12, features=TREND, features_position="inline"),
            tile(f"{S}_tlakovy_trend"),
            tile(f"{S}_index_tepelneho_komfortu"),
        ]},
        {"type": "grid", "cards": [
            head("Vietor", "mdi:weather-windy"),
            {"type": "gauge", "entity": f"{S}_rychlost_vetra", "name": "Rýchlosť vetra",
             "min": 0, "max": 80, "needle": True,
             "severity": {"green": 0, "yellow": 20, "red": 50},
             "grid_options": {"columns": 12, "rows": 3}},
            tile(f"{S}_rychlost_vetra_naraz", 6, name="Náraz"),
            tile(f"{S}_smer_vetra_text", 6, name="Smer", icon="mdi:compass-outline"),
            tile(f"{S}_sila_vetra_beaufort", 12),
        ]},
        {"type": "grid", "cards": [
            head("Zrážky", "mdi:weather-pouring"),
            tile(f"{B}_detekcia_dazda", 6),
            tile(f"{S}_intenzita_zrazok", 6),
            tile(f"{S}_intenzita_zrazok_text", 12),
            tile(f"{S}_celkove_zrazky", 6),
            tile(f"{S}_vlhkost_dazdoveho_senzora", 6,
                 features=[{"type": "bar-gauge", "min": 0, "max": 100}]),
        ]},
        {"type": "grid", "cards": [
            head("Slnko a vzduch", "mdi:white-balance-sunny"),
            {"type": "gauge", "entity": f"{S}_uv_index", "name": "UV index",
             "min": 0, "max": 12, "needle": True,
             "severity": {"green": 0, "yellow": 3, "red": 6},
             "grid_options": {"columns": 12, "rows": 3}},
            tile(f"{S}_intenzita_svetla", 6, features=TREND, features_position="inline"),
            tile(f"{S}_absolutna_vlhkost", 6),
        ]},
        {"type": "grid", "column_span": 2, "cards": [
            head("Výstrahy", "mdi:alert-outline"),
            {"type": "conditional",
             "conditions": [{"condition": "state", "entity": f"{B}_vystraha_burka", "state": "on"}],
             "card": tile(f"{B}_vystraha_burka", 12, color="red")},
            {"type": "conditional",
             "conditions": [{"condition": "state", "entity": f"{B}_riziko_mrazu", "state": "on"}],
             "card": tile(f"{B}_riziko_mrazu", 12, color="cyan")},
            {"type": "conditional",
             "conditions": [{"condition": "state", "entity": f"{B}_predikcia_dazda_tlak", "state": "on"}],
             "card": tile(f"{B}_predikcia_dazda_tlak", 12, color="blue")},
            {"type": "conditional",
             "conditions": [{"condition": "state", "entity": f"{B}_kriticka_bateria", "state": "on"}],
             "card": tile(f"{B}_kriticka_bateria", 12, color="red")},
            {"type": "conditional",
             "conditions": [{"condition": "state", "entity": f"{B}_chyba_senzorov", "state": "on"}],
             "card": tile(f"{B}_chyba_senzorov", 12, color="orange")},
            {"type": "conditional",
             "conditions": [
                 {"condition": "state", "entity": f"{B}_vystraha_burka", "state": "off"},
                 {"condition": "state", "entity": f"{B}_riziko_mrazu", "state": "off"},
                 {"condition": "state", "entity": f"{B}_predikcia_dazda_tlak", "state": "off"},
                 {"condition": "state", "entity": f"{B}_kriticka_bateria", "state": "off"},
             ],
             "card": {"type": "markdown", "text_only": True,
                      "content": "✅ Žiadne aktívne výstrahy."}},
        ]},
    ],
}

# ------------------------------------------------------------------ GRAFY
def hist(entities, hours=48, rows=6):
    return {"type": "history-graph", "hours_to_show": hours, "entities": entities,
            "grid_options": {"columns": "full", "rows": rows}}

grafy = {
    "title": "Grafy", "path": "grafy", "type": "sections",
    "icon": "mdi:chart-line", "max_columns": 2,
    "sections": [
        {"type": "grid", "cards": [
            head("Teplota", "mdi:thermometer-lines"),
            hist([
                {"entity": f"{S}_vonkajsia_teplota", "name": "Teplota", "color": "red"},
                {"entity": f"{S}_pocitova_teplota", "name": "Pocitová", "color": "orange"},
                {"entity": f"{S}_rosny_bod", "name": "Rosný bod", "color": "blue"},
            ]),
        ]},
        {"type": "grid", "cards": [
            head("Vlhkosť a tlak", "mdi:water-percent"),
            hist([
                {"entity": f"{S}_vonkajsia_vlhkost", "name": "Vlhkosť", "color": "teal"},
                {"entity": f"{S}_absolutna_vlhkost", "name": "Absolútna", "color": "green"},
            ]),
            {"type": "statistics-graph", "entities": [f"{S}_tlak_hladina_mora"],
             "stat_types": ["mean", "min", "max"], "period": "hour", "days_to_show": 7,
             "chart_type": "line", "grid_options": {"columns": "full", "rows": 6}},
        ]},
        {"type": "grid", "cards": [
            head("Vietor", "mdi:weather-windy"),
            hist([
                {"entity": f"{S}_rychlost_vetra", "name": "Rýchlosť", "color": "purple"},
                {"entity": f"{S}_rychlost_vetra_naraz", "name": "Náraz", "color": "deep-purple"},
            ]),
        ]},
        {"type": "grid", "cards": [
            head("Zrážky", "mdi:weather-pouring"),
            head("Denné úhrny z kumulatívneho počítadla", style="subtitle"),
            {"type": "statistics-graph", "entities": [f"{S}_celkove_zrazky"],
             "stat_types": ["change"], "period": "day", "days_to_show": 30,
             "chart_type": "bar", "grid_options": {"columns": "full", "rows": 6}},
        ]},
        {"type": "grid", "cards": [
            head("Slnko a UV", "mdi:sun-wireless-outline"),
            hist([
                {"entity": f"{S}_uv_index", "name": "UV index", "color": "amber"},
                {"entity": f"{S}_intenzita_svetla", "name": "Osvetlenie", "color": "yellow"},
            ]),
        ]},
        {"type": "grid", "cards": [
            head("Batéria", "mdi:battery-charging"),
            hist([
                {"entity": f"{S}_uroven_baterie", "name": "Úroveň", "color": "green"},
                {"entity": f"{S}_napatie_baterie", "name": "Napätie", "color": "grey"},
            ], hours=168),
        ]},
    ],
}

# ---------------------------------------------------------------- STANICA
stanica = {
    "title": "Stanica", "path": "stanica", "type": "sections",
    "icon": "mdi:memory", "max_columns": 3,
    "sections": [
        {"type": "grid", "cards": [
            head("Stav", "mdi:heart-pulse"),
            tile(f"{B}_status_stanice", 6),
            tile(f"{S}_rezim_stanice", 6),
            tile(f"{S}_uroven_baterie", 12,
                 features=[{"type": "bar-gauge", "min": 0, "max": 100}]),
            tile(f"{S}_napatie_baterie", 6),
            tile(f"{S}_cas_behu", 6),
            tile(f"{S}_pocet_bootov", 6),
            tile(f"{S}_teplota_cpu", 6),
        ]},
        {"type": "grid", "cards": [
            head("Sieť", "mdi:wifi"),
            tile(f"{S}_kvalita_wifi", 12,
                 features=[{"type": "bar-gauge", "min": 0, "max": 100}]),
            tile(f"{S}_wifi_signal_dbm", 6),
            tile(f"{S}_wifi_zlyhania_za_sebou", 6),
            head("Diagnostika", "mdi:stethoscope"),
            tile(f"{B}_chyba_senzorov", 6),
            tile(f"{S}_chyby_senzorov", 6),
            tile(f"{S}_napatie_dazdoveho_senzora", 6),
            tile(f"{S}_smer_vetra_uhol", 6),
        ]},
        {"type": "grid", "cards": [
            head("Ovládanie", "mdi:tune"),
            head("OTA režim udrží stanicu hore, aby sa dal nahrať firmvér",
                 style="subtitle"),
            tile(f"{SW}_ota_rezim_nespat", 12, features=[{"type": "toggle"}]),
            tile(f"{SW}_manualne_napajanie_senzorov", 12, features=[{"type": "toggle"}]),
            press(f"{BT}_vynutit_deep_sleep", "mdi:sleep", "Uspať teraz",
                  "Naozaj uspať stanicu?"),
            press(f"{BT}_reset_diagnostiky", "mdi:restore", "Reset diagnostiky"),
            press(f"{BT}_reset_pocitadla_zrazok", "mdi:water-off", "Vynulovať zrážky",
                  "Naozaj vynulovať kumulatívny súčet zrážok?"),
            tile(f"{SW}_restartovat_stanicu", 12),
            head("Prahy", "mdi:sine-wave"),
            tile(f"{NU}_prah_trendu_tlaku", 12,
                 features=[{"type": "numeric-input", "style": "slider"}]),
            tile(f"{NU}_prah_vlhkosti_pre_dazd", 12,
                 features=[{"type": "numeric-input", "style": "slider"}]),
            head("Súvisiaca automatizácia", style="subtitle"),
            {"type": "tile", "entity": "automation.deep_sleep_meteostanica",
             "features": [{"type": "toggle"}], "grid_options": {"columns": 12}},
        ]},
    ],
}

CONFIG = {"views": [uvod, grafy, stanica]}
URL_PATH = "meteo-stanica"


def ws(payload):
    r = subprocess.run([sys.executable, "ha_ws.py", "--file", "/dev/stdin"],
                       input=json.dumps(payload), capture_output=True, text=True)
    return json.loads(r.stdout or '{"success": false}')


if __name__ == "__main__":
    existing = ws({"type": "lovelace/dashboards/list"})
    paths = {d["url_path"] for d in existing.get("result", [])}
    if URL_PATH not in paths:
        r = ws({"type": "lovelace/dashboards/create", "url_path": URL_PATH,
                "title": "Meteostanica", "icon": "mdi:weather-partly-cloudy",
                "show_in_sidebar": True, "require_admin": False})
        print("create:", r.get("success"), r.get("error", ""))
    else:
        print("dashboard už existuje, iba prepíšem obsah")
    r = ws({"type": "lovelace/config/save", "url_path": URL_PATH, "config": CONFIG})
    print("save:", r.get("success"), r.get("error", ""))
    print("views:", [v["title"] for v in CONFIG["views"]])
