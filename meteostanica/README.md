# Vonkajšia meteostanica — ESPHome v3.0.0

Solárne napájaná meteostanica na ESP32 s adaptívnym deep sleep, integrovaná do
Home Assistantu cez natívne ESPHome API.

**Meria:** teplota, vlhkosť, tlak (BME280) · osvetlenie a UV index (LTR390) ·
rýchlosť a smer vetra · zrážky (preklopná nádobka + analógová doštička) ·
napätie batérie.

**Odvodzuje:** rosný bod, absolútnu vlhkosť, pocitovú teplotu, index tepelného
komfortu, tlak na hladine mora, tlakový trend (lineárna regresia), predikciu
dažďa, výstrahu na búrku a mráz, Beaufortovu stupnicu, odporúčanie oblečenia.

---

## Štruktúra

```
meteostanica/
├── meteostanica.yaml          # hlavný súbor: LEN substitúcie + zoznam balíčkov
├── secrets.yaml.example       # šablóna, skopíruj na secrets.yaml
└── packages/
    ├── core.yaml              # boot sekvencia, logger, globálne premenné
    ├── network.yaml           # WiFi, API (šifrované), OTA
    ├── power.yaml             # napájacie rails, batéria, deep sleep
    ├── sensors_i2c.yaml       # BME280, LTR390
    ├── sensors_wind_rain.yaml # anemometer, korouhvička, zrážkomer
    ├── derived.yaml           # odvodené veličiny a výstrahy
    ├── text_sensors.yaml      # textové zhrnutia pre dashboard
    ├── controls.yaml          # prepínače, tlačidlá, konfiguračné čísla
    ├── diagnostics.yaml       # uptime, RSSI, počítadlá chýb
    └── scripts.yaml           # logika celého cyklu bdenia
```

Všetko laditeľné (piny, prahy, kalibrácia, časy spánku) je v sekcii
`substitutions` v `meteostanica.yaml`. Do súborov v `packages/` by nemalo byť
potrebné siahať pri bežnom ladení.

---

## Inštalácia

```bash
cp secrets.yaml.example secrets.yaml
```

Vyplň `secrets.yaml` (WiFi, IP, API kľúč, OTA heslo). API kľúč vygeneruješ:

```bash
python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
```

Skontroluj konfiguráciu bez kompilácie:

```bash
esphome config meteostanica.yaml
```

Skompiluj a nahraj (prvýkrát cez USB):

```bash
esphome run meteostanica.yaml
```

> `secrets.yaml` je v `.gitignore`. Nikdy ho necommituj.

---

## Zapojenie

| GPIO   | Funkcia            | Pripojené na |
|--------|--------------------|--------------|
| GPIO22 | I2C SDA            | BME280 (0x76), LTR390 (0x53) |
| GPIO21 | I2C SCL            | BME280, LTR390 |
| GPIO19 | výstup             | napájanie I2C vetvy (senzory **aj pull-upy**) |
| GPIO18 | výstup             | napájanie analógovej dažďovej doštičky |
| GPIO35 | ADC1               | delič napätia batérie (2× 100 kΩ) |
| GPIO34 | ADC1               | analógová dažďová doštička |
| GPIO33 | ADC1               | korouhvička (delič s 10 kΩ na GND) |
| GPIO25 | vstup, pull-up     | anemometer (jazýčkový kontakt na GND) |
| GPIO26 | vstup, pull-up, RTC| zrážkomer (preklopná nádobka na GND) |

**Dôležité:** pull-up rezistory I2C zbernice musia byť napájané z GPIO19, nie
z trvalej 3V3. Inak sa senzory napájajú parazitne cez ochranné diódy na SDA/SCL
a nikdy sa naozaj nevypnú.

Všetky ADC vstupy sú zámerne na ADC1 — ADC2 na ESP32 nie je použiteľné, keď beží
WiFi.

---

## Ako beží jeden cyklus

```
prebudenie
   │
   ├─ on_boot / priorita 750    globals sú obnovené, GPIO fungujú,
   │                            I2C senzory ešte NEBEŽALI setup()
   │                            → zapni napájacie rails, počkaj 120 ms
   │
   ├─ (ESPHome inicializuje komponenty: I2C 600, WiFi 250, ...)
   │
   └─ on_boot / priorita -100   → failsafe_guard + main_cycle
                                    1. batéria (ešte pred záťažou rádia)
                                    2. BME280 + LTR390
                                    3. analógové vstupy, impulzné počítadlá
                                    4. účtovníctvo (jediný zápis do globals)
                                    5. tlakový trend
                                    6. voľba režimu spánku
                                    7. publikovanie do HA
                                    8. čakanie na WiFi + API
                                    9. deep sleep
```

Typické okno bdenia je **8–12 s**.

### Režimy spánku

| Režim   | Trvanie | Kedy |
|---------|---------|------|
| STORM   | 2 min   | dážď / predikcia dažďa / búrka / vietor > 15 km/h, batéria > 30 % |
| PERF    | 5 min   | batéria > 80 % a pokoj |
| Normal  | 10 min  | inak |
| ECO     | 30 min  | batéria < 20 % (má prednosť pred všetkým) |

Pri zlyhaní siete: 5 min, po 5 neúspechoch za sebou 30 min.
Ak sa cyklus zasekne, `failsafe_guard` uspí stanicu po 4 minútach.

### OTA aktualizácia

Stanica je online len ~10 s v každom cykle. Na nahratie firmvéru:

1. V HA zapni prepínač **„OTA režim (nespať)"**.
2. Počkaj na najbližšie prebudenie (max. dĺžka aktuálneho režimu).
3. Stanica zostane hore — spusti `esphome run meteostanica.yaml`.
4. Prepínač vypni.

Stav prepínača prežije deep sleep (`restore_mode: RESTORE_DEFAULT_OFF`).

---

## Tipy pre Home Assistant

Denné a mesačné úhrny zrážok rieš cez `utility_meter` nad entitou
`sensor.celkove_zrazky` (má `state_class: total_increasing`) — prežije to
reflash aj reštart, na rozdiel od počítania priamo na ESP:

```yaml
utility_meter:
  zrazky_denne:
    source: sensor.celkove_zrazky
    cycle: daily
  zrazky_mesacne:
    source: sensor.celkove_zrazky
    cycle: monthly
```

Hysterézu pri výstrahách (mráz, búrka) rob v automatizácii cez `for:`. Na
zariadení to nemá zmysel — pri deep sleep sa žiadny `delayed_on` filter dlhší
než okno bdenia nikdy nedokončí.

---

## Čo sa zmenilo oproti v2.4 / v2.5

| # | Problém vo v2.x | Oprava |
|---|-----------------|--------|
| 1 | `deep_sleep` nemal default `sleep_duration`. Tlačidlo „Vynútiť Deep Sleep" hneď po boote uspalo stanicu **navždy**, až do manuálneho resetu. | `sleep_duration: 10min` ako bezpečný default. |
| 2 | Absolútna vlhkosť používala konštantu `2165` namiesto `216.7` — hodnoty boli **10× vyššie**. | Opravená konštanta, doplnené odvodenie v komentári. |
| 3 | Beaufortova stupnica bola posunutá o stupeň (12–19 km/h hlásila ako B4, správne je B3). | Prepísaná podľa oficiálnych hraníc, doplnené stupne 11 a 12. |
| 4 | `binary_sensor.template` **nie je** polling komponent — jeho lambda beží v `loop()`. Lambda `rain_prediction` pritom zapisovala do histórie tlaku, takže tú prepisovala stovky krát za sekundu a história bola nepoužiteľná. | Binárne senzory sú bez vedľajších efektov. Do globálnych premenných zapisuje výhradne `main_cycle`. |
| 5 | `frost_risk` mal `delayed_on: 30s`, `storm_warning` `delayed_on: 60s` — pri okne bdenia ~10 s sa **nikdy nezopli**. | Filtre odstránené, hysteréza patrí do HA. |
| 6 | Trend tlaku sa počítal z `on_value` tlaku, teda **predtým**, než sa história aktualizovala. Časová os používala číslo bootu prenásobené *aktuálnou* dĺžkou spánku, čo bolo pri striedaní režimov (2/5/10/30 min) nesprávne. | Poradie je pevne dané v `main_cycle`. Časová os je monotónny `station_seconds` v sekundách. Regresia je centrovaná okolo priemeru kvôli presnosti `float`. |
| 7 | `deep_sleep.prevent` v `on_client_connected` nefungoval — akcia `deep_sleep.enter` volá `begin_sleep(manual = true)`, ktorá príznak `prevent_` obchádza. **OTA okno reálne neexistovalo.** | Explicitný prepínač „OTA režim (nespať)", ktorý sa kontroluje pred každým uspaním aj vo failsafe. |
| 8 | `api:` bez šifrovania, `ota:` bez hesla, AP heslo a statická IP natvrdo vo verejnom repozitári. | Všetko v `secrets.yaml`, API šifrované, OTA s heslom. |
| 9 | Napájanie senzorov sa zapínalo v `on_boot` s prioritou 600 — rovnakou, akú má setup() BME280. Poradie bolo nedeterministické, preto bol potrebný manuálny I2C „recovery" s power-cyklovaním. | Rails sa zapínajú pri priorite 750, teda spoľahlivo **pred** setup() I2C komponentov. Celý recovery aparát je zbytočný a odstránený. |
| 10 | ~5,5 s zbytočného čakania v okne bdenia (2 s po zapnutí napájania, 3× čítanie BME280 so 150 ms pauzami, 3 s pred spánkom) z ~12 s cyklu. | 120 ms + jedno zahrievacie čítanie + 600 ms na doručenie stavov. |
| 11 | Zrážkomer: `update_interval: 60s` sa v ~10 s okne nikdy nespustil a `pulse_counter` total sa **resetoval pri každom boote** — entita bola v štatistikách HA nepoužiteľná. | Súčet sa kumuluje v RTC premennej `rain_tips_total`, entita má `state_class: total_increasing`. Intenzita sa počíta ako skutočný priemer za uplynulý interval. |
| 12 | `use_pcnt: true` obmedzuje `internal_filter` na ~13 µs (limit PCNT hardvéru) — zákmity jazýčkových kontaktov sa počítali ako pulzy. | `use_pcnt: false`, debounce 5 ms (vietor) a 200 ms (zrážkomer). |
| 13 | UV index sa počítal ako `raw / 170` — magická konštanta viazaná na konkrétny gain a rozlíšenie. | Použitý natívny výstup `uv_index:` komponentu `ltr390`, vrátane `window_correction_factor`. |
| 14 | `wind_direction_angle` nebol v zozname aktualizácií a mal default 60 s polling — **nikdy sa nepublikoval**. | `update_interval: never` + explicitné publikovanie v `publish_all`. |
| 15 | Chýbali `device_class` / `state_class` na väčšine template senzorov, takže HA z nich nerobil dlhodobú štatistiku. | Doplnené všade (`precipitation`, `precipitation_intensity`, `wind_speed`, `voltage`, `atmospheric_pressure`, …). |
| 16 | `uptime` s `update_interval: 1s` = ~10 zbytočných publikácií za cyklus do HA recordera. | `never`, publikuje sa raz. |
| 17 | Vedľajšie efekty vo `filters:` (počítadlo chýb sa nulovalo pri každom platnom čítaní teploty, takže bolo prakticky vždy 0). | Filtre iba validujú, počítadlo sa vyhodnocuje raz za cyklus. |
| 18 | Mŕtvy kód: `i2c_restart_attempts`, `pressure_threshold` (entita, ktorá sa nikde nepoužívala), `- offset: 0.0`, `uspat_ltr390`, `interval: 15s` duplikujúci failsafe. | Odstránené. `pressure_threshold` je teraz reálne zapojený do predikcie dažďa. |
| 19 | `logger: level: WARN`, ale konfigurácia bola plná `ESP_LOGI` — všetky tie logy boli mŕtve. | `INFO` s per-tag stlmením hlučných komponentov. |
| 20 | `abs()` na `float` funguje len vďaka Arduino makru. | `fabsf()` / `powf()` / `expf()` / `logf()` — konfigurácia je pripravená aj na `framework: esp-idf`. |

---

## Známe obmedzenia a ďalší krok

### Impulzné senzory počas spánku

Toto je najväčšie zostávajúce obmedzenie. Anemometer a zrážkomer počítajú
**len počas okna bdenia**, teda zhruba 2 % času (v STORM režime ~10 %).
Rýchlosť vetra je vzorka, nie priemer; „náraz" je maximum z 2–3 vzoriek.

Riešenie pre zrážkomer — GPIO26 je RTC pin, takže vie prebudiť ESP z deep
sleepu (`ext0`):

```yaml
deep_sleep:
  wakeup_pin:
    number: GPIO26
    mode: INPUT_PULLUP
    inverted: true
  wakeup_pin_mode: IGNORE
```

V `on_boot` s prioritou 750 (globals sú obnovené, WiFi sa ešte nespustilo)
zisti príčinu prebudenia cez `esp_sleep_get_wakeup_cause()`; ak to bol pin,
inkrementuj `rain_tips_total` a okamžite zaspi späť — bez zapínania senzorov
a bez WiFi. Jedno preklopenie tak stojí ~300 ms behu namiesto celého cyklu.
Aby počas trvalého dažďa stanica aj niečo nahlásila, po N preklopeniach
(napr. 5) sprav namiesto návratu do spánku plný cyklus.

Pre anemometer sa to takto riešiť nedá (príliš veľa pulzov) — buď predĺž okno
bdenia, alebo použi externý čítač.

### Hardvér

- **`board: esp32dev`** (bežný DevKit) má AMS1117 LDO s kľudovým prúdom ~5 mA
  a USB-UART prevodník. Deep sleep tak berie **8–15 mA namiesto ~10 µA**, čo je
  200–350 mAh/deň — rádovo viac než všetko meranie dokopy. Kým je tam DevKit,
  adaptívny spánok je len kozmetika. Holý ESP32-WROOM modul s LDO typu HT7333
  alebo TPS7A02 (prípadne prechod na ESP32-C3) je najväčší reálny zisk.
- **Korouhvička** je elektricky na hrane: pri 10 kΩ na GND a odporoch
  688 Ω – 120 kΩ vychádzajú napätia 0,25 – 3,08 V, ale ADC ESP32 pri 12 dB je
  použiteľné zhruba do 2,45 V. Smery s odporom pod ~2,2 kΩ (67,5°, 90°, 112,5°)
  padajú do saturácie. Zníž odpor na ~3,3 kΩ a namiesto počítaného odporu si
  odmeraj skutočné napätia všetkých 16 polôh.
- **Delič batérie** (2× 100 kΩ) ťahá trvalo ~20 µA. Ak sa optimalizuje spotreba
  do konca, spínaj ho MOSFETom.
- **Li-ion sa nesmie nabíjať pod 0 °C** — pri solárnom nabíjaní zváž nabíjačku
  s NTC termistorom.

### Ostatné

- `internal_temperature` na pôvodnom ESP32 číta z PHY bloku a je len
  orientačná — nie je to teplota okolia.
- História tlaku (8 vzoriek) pokrýva 40 min v PERF režime až 4 h v ECO režime.
  Trend v hPa/h je preto v ECO režime hladší a pomalší.
