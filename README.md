# AI Fitness — Auslastung & Check-ins für Home Assistant

[![hacs][hacs-badge]][hacs]

Bringt die **Live-Auslastung** deines AI-Fitness-Studios (all inclusive Fitness)
und optional deine **Check-in-Historie** nach Home Assistant.

Die Auslastung kommt aus der **öffentlichen** API von `ai-fitness.de` — kein
Account, kein Login, kein API-Key; dieselbe Quelle wie das Auslastungs-Widget auf
den Studio-Seiten. Für die Check-ins meldest du dich zusätzlich mit deinem
App-Account an — das ist optional, die Auslastung funktioniert ohne.

## Features

Die Integration kennt **zwei Eintragstypen**, die sich frei kombinieren lassen:

| Eintrag | Login? | Liefert |
|---------|--------|---------|
| **Studio-Auslastung** | nein | Live-Auslastung eines Standorts — beliebig oft hinzufügbar |
| **Mein Account** | ja | Deine Check-in-Historie — einmal pro Account |

Check-ins sind account-weit (du kannst überall einchecken), die Auslastung ist
pro Studio. Deshalb zwei Typen statt einem kombinierten Eintrag — sonst hättest
du bei mehreren Studios doppelte Check-in-Sensoren.

### Studio-Auslastung (ohne Login)

- **Auslastung in %** für den aktuellen Zeitslot
- **Auslastungsstufe** (`LOW` / `MEDIUM` / `HIGH`) als Enum-Sensor
- **Tagesmaximum** — höchster gemessener Wert des heutigen Tages (standardmäßig deaktiviert)
- **Geöffnet** als Binary-Sensor
- Die komplette Tageskurve als Attribut — direkt nutzbar für ApexCharts
- Mehrere Studios parallel: einfach die Integration mehrfach hinzufügen
- Studioliste wird **live** geladen — neue Standorte tauchen ohne Update auf

### Mein Account (mit Login)

- **Check-ins dieses Jahr / diesen Monat**
- **Letzter Check-in** als Zeitstempel, inkl. Studio und Besuchsdauer
- **Gerade im Studio** als Binary-Sensor — die Drehtür weiss, ob du noch drin bist
- Monats-Breakdown als Attribut für ein Balkendiagramm

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

Im ersten Schritt wählst du zwischen **Studio-Auslastung** und **Mein Account**.

### Studio-Auslastung

Es gibt drei Wege zum Studio:

| Weg | Beschreibung |
|-----|--------------|
| **Studios in meiner Nähe** | Sortiert nach Entfernung zu deinem HA-Standort, mit km-Angabe |
| **Nach Name oder Ort suchen** | Freitextsuche über Studioname, Ort und PLZ |
| **Studio-ID eingeben** | Direkt die numerische ID, falls du sie schon kennst |

### Mein Account

E-Mail und Passwort aus der AI-Fitness-App. Die Zugangsdaten werden lokal im
Config-Entry gespeichert und ausschliesslich gegen die offizielle App-API
verwendet. Läuft die Anmeldung ab, fragt Home Assistant per Reauth-Dialog nach.

### Intervall

Das Abfrageintervall lässt sich jederzeit über *Konfigurieren* am Eintrag ändern
(Standard: **5 min** für Auslastung, **30 min** für Check-ins).

> Die Auslastung wird serverseitig **alle paar Minuten** aktualisiert — nicht nur
> stündlich. Gemessen: 17 % → 18 % innerhalb desselben Stundenslots. Ein Intervall
> von 2–5 Minuten liefert also echten Mehrwert.

## Entitäten

Pro Studio wird ein Gerät mit diesen Entitäten angelegt:

| Entität | Typ | Beschreibung |
|---------|-----|--------------|
| `sensor.<studio>_auslastung` | `%` | Auslastung im aktuellen Stundenslot |
| `sensor.<studio>_auslastungsstufe` | Enum | `LOW`, `MEDIUM` oder `HIGH` |
| `sensor.<studio>_tagesmaximum` | `%` | Höchstwert des Tages (deaktiviert per Default) |
| `binary_sensor.<studio>_geoffnet` | `opening` | Ob das Studio gerade geöffnet hat |

Beim Account-Eintrag:

| Entität | Typ | Beschreibung |
|---------|-----|--------------|
| `sensor.<account>_checkins_dieses_jahr` | Zähler | Besuche im laufenden Jahr (Attribut `monthly`) |
| `sensor.<account>_checkins_diesen_monat` | Zähler | Besuche im laufenden Monat |
| `sensor.<account>_letzter_checkin` | `timestamp` | Beginn des letzten Besuchs |
| `sensor.<account>_letztes_studio` | Text | Wo der letzte Besuch war |
| `sensor.<account>_dauer_letzter_besuch` | `duration` (min) | Länge des letzten Besuchs |
| `binary_sensor.<account>_gerade_im_studio` | `presence` | Eingecheckt und noch nicht ausgecheckt |

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

### Auslastung — öffentlich

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

### Check-ins — authentifiziert

Der Account-Teil spricht dieselbe API wie die offizielle App
(`api-allinclusive.tocc.dirs21.de`, OAuth2 Password Grant). Das Token gilt 24 h
und wird über den Refresh-Token erneuert; der Refresh-Token rotiert bei jeder
Nutzung und wird im Config-Entry mitgeführt.

## Hinweise

- Ausserhalb der Öffnungszeiten markiert die API keinen Slot als aktuell. Die
  Auslastung ist dann `unknown` und `binary_sensor` steht auf `off`.
- Die Auslastung ist in Stundenslots gebucketet, der **aktuelle** Slot wird aber
  alle paar Minuten nachgeführt. 2–5 Minuten Intervall sind sinnvoll, häufiger
  bringt nichts. Bitte fair pollen.
- Check-ins ändern sich höchstens ein paar Mal am Tag — 30 Minuten reichen dort.
- Diese Integration ist ein inoffizielles Community-Projekt und steht in keiner
  Verbindung zu AI Fitness, Magicline oder ABC Fitness. Das Logo gehört der
  AI Fitness / all inclusive Fitness Deutschland GmbH und wird hier
  ausschliesslich zur Kennzeichnung der Datenquelle verwendet.

## Icon

Die Brand-Assets liegen unter [`custom_components/ai_fitness/brand/`](custom_components/ai_fitness/brand/)
(`icon.png` 256px, `icon@2x.png` 512px, dazu `logo*.png`) — das Rundlogo der App,
transparent, beschnitten.

> Home Assistant und HACS laden Integrations-Icons nicht aus dem Repository,
> sondern von `brands.home-assistant.io`. Damit das Icon in der Oberfläche
> erscheint, müssen die Dateien per PR nach
> [home-assistant/brands](https://github.com/home-assistant/brands) unter
> `custom_integrations/ai_fitness/` eingereicht werden. Bis dahin zeigt HA das
> Standard-Puzzleteil — rein kosmetisch, die Integration funktioniert normal.

## Lizenz

MIT — siehe [LICENSE](LICENSE).

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
