# Dashboard pre Home Assistant

`build_dashboard.py` vytvorí (alebo prepíše) dashboard **Meteostanica**
na `/meteo-stanica` — tri pohľady: Prehľad, Grafy, Stanica.

```bash
export HA_URL=http://192.168.0.10:8123     # ak je iná adresa
python3 build_dashboard.py
```

Token sa číta z `~/.ha_token` (long-lived access token z profilu HA).
`ha_ws.py` je len tenký WebSocket klient — Lovelace sa cez REST API meniť nedá.

Skript je idempotentný: ak dashboard existuje, iba prepíše jeho obsah.
Ručné úpravy v UI teda prepíše — po ladení v UI si config vytiahni cez
`python3 ha_ws.py lovelace/config '{"url_path":"meteo-stanica"}'`.

## Entity

Prefix je `meteostanica_vonku_1_`, lebo tak sa zariadenie volá v HA
(*MeteoStanica - Vonku 1*) — nie podľa `dev_name` z ESPHome konfigurácie.
Ak zariadenie v HA premenuješ, prefix nových entít sa zmení a konštantu `E`
v skripte treba upraviť.

Deväť entít vznikne až po nahratí firmvéru v3.0: rýchlosť vetra a náraz,
`chyba_senzorov`, `ota_rezim_nespat`, prah trendu tlaku a tri tlačidlá.
Do tej doby sa na dashboarde zobrazia ako nedostupné.
