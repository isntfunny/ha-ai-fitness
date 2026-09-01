# AI Fitness — Studioauslastung für Home Assistant

[![hacs][hacs-badge]][hacs]

Zeigt die **Live-Auslastung** deines AI-Fitness-Studios (all inclusive Fitness) in
Home Assistant an.

Die Integration nutzt die **öffentliche** Auslastungs-API von `ai-fitness.de` —
kein Account, kein Login, kein API-Key. Es ist dieselbe Quelle, die auch das
Auslastungs-Widget auf den Studio-Seiten speist.

## Features

- **Auslastung in %** für den aktuellen Zeitslot
- **Auslastungsstufe** (`LOW` / `MEDIUM` / `HIGH`) als Enum-Sensor
- **Tagesmaximum** — höchster gemessener Wert des heutigen Tages (standardmäßig deaktiviert)
- **Geöffnet** als Binary-Sensor
- Die komplette Tageskurve als Attribut — direkt nutzbar für ApexCharts
- Mehrere Studios parallel: einfach die Integration mehrfach hinzufügen
- Studioliste wird **live** geladen — neue Standorte tauchen ohne Update auf

## Installation

### HACS (empfohlen)

1. HACS → ⋮ → *Custom repositories*
2. Repository: `https://github.com/isntfunny/ha-ai-fitness`, Kategorie *Integration*
3. *AI Fitness* installieren, Home Assistant neu starten

### Manuell

Den Ordner `custom_components/ai_fitness` nach `<config>/custom_components/`
kopieren und Home Assistant neu starten.

## Einrichtung

*Einstellungen → Geräte & Dienste → Integration hinzufügen → **AI Fitness***

Es gibt drei Wege zum Studio:

| Weg | Beschreibung |
|-----|--------------|
| **Studios in meiner Nähe** | Sortiert nach Entfernung zu deinem HA-Standort, mit km-Angabe |
| **Nach Name oder Ort suchen** | Freitextsuche über Studioname, Ort und PLZ |
| **Studio-ID eingeben** | Direkt die numerische ID, falls du sie schon kennst |

Das Abfrageintervall (Standard: 5 Minuten) lässt sich jederzeit über
*Konfigurieren* am Integrationseintrag ändern.

## Entitäten

Pro Studio wird ein Gerät mit diesen Entitäten angelegt:

| Entität | Typ | Beschreibung |
|---------|-----|--------------|
| `sensor.<studio>_auslastung` | `%` | Auslastung im aktuellen Stundenslot |
| `sensor.<studio>_auslastungsstufe` | Enum | `LOW`, `MEDIUM` oder `HIGH` |
| `sensor.<studio>_tagesmaximum` | `%` | Höchstwert des Tages (deaktiviert per Default) |
| `binary_sensor.<studio>_geoffnet` | `opening` | Ob das Studio gerade geöffnet hat |

### Attribute des Auslastungs-Sensors

| Attribut | Beschreibung |
|----------|--------------|
| `level` | Stufe des aktuellen Slots |
| `slot_start` / `slot_end` | Zeitfenster des aktuellen Werts |
| `is_open` | Studio geöffnet |
| `opens_at` / `closes_at` | Öffnungszeiten heute |
| `peak_percentage` / `peak_start` | Tageshöchstwert und wann |
| `items` | Alle Slots des Tages |
| `elapsed_items` | Nur die bereits abgelaufenen Slots |

> **Wichtig zu `items`:** Die API liefert Messwerte nur für vergangene und den
> aktuellen Slot. Slots in der Zukunft kommen mit `0 %` zurück — das ist
> **keine** Prognose. Für Diagramme ist `elapsed_items` in der Regel die
> richtige Wahl, sonst fällt die Kurve am Ende künstlich auf null.

## Beispiel: Tageskurve mit ApexCharts

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Studioauslastung heute
series:
  - entity: sensor.ai_fitness_bochum_auslastung
    name: Auslastung
    type: column
    data_generator: |
      return entity.attributes.elapsed_items.map(i => [
        new Date(new Date().toDateString() + " " + i.startTime).getTime(),
        i.percentage
      ]);
```

## Beispiel: Benachrichtigung wenn es leer ist

```yaml
automation:
  - alias: "Gym ist leer"
    triggers:
      - trigger: numeric_state
        entity_id: sensor.ai_fitness_bochum_auslastung
        below: 25
    conditions:
      - condition: time
        after: "17:00:00"
        before: "21:00:00"
      - condition: state
        entity_id: binary_sensor.ai_fitness_bochum_geoffnet
        state: "on"
    actions:
      - action: notify.mobile_app
        data:
          message: >-
            Nur {{ states('sensor.ai_fitness_bochum_auslastung') }}% los im Studio.
```

## Wie es funktioniert

Zwei öffentliche Endpoints, beide ohne Authentifizierung:

```
GET https://www.ai-fitness.de/connect/v2/studio
GET https://www.ai-fitness.de/connect/v1/studio/{studioId}/utilization
```

Der erste liefert alle Studios inklusive Koordinaten und Öffnungszeiten (deshalb
braucht die Integration keine gepflegte Studioliste), der zweite die Auslastung.

> ⚠️ Wer die API selbst anspricht: **niemals `Accept: application/json` senden** —
> der Upstream antwortet darauf mit `406 Not Acceptable`. Mit `Accept: */*` oder
> ganz ohne Accept-Header funktioniert es.

Dahinter steckt die **Magicline**-Studioverwaltung, über die auch die Check-ins
am Drehkreuz laufen — daher die Live-Daten.

## Hinweise

- Ausserhalb der Öffnungszeiten markiert die API keinen Slot als aktuell. Die
  Auslastung ist dann `unknown` und `binary_sensor` steht auf `off`.
- Die Daten sind stundenweise aufgelöst; ein Intervall unter 5 Minuten bringt
  keine zusätzliche Genauigkeit. Bitte fair pollen.
- Diese Integration ist ein inoffizielles Community-Projekt und steht in keiner
  Verbindung zu AI Fitness, Magicline oder ABC Fitness.

## Lizenz

MIT — siehe [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
