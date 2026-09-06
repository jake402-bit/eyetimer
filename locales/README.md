# Traduzioni / Translations

*(English below)*

## Italiano

Questa cartella contiene le traduzioni dell'interfaccia di **Timer Occhi
20-20-20** (in inglese: *20-20-20 Eye Timer*). Ogni file è un JSON con lo
stesso insieme di chiavi; il nome del file (senza `.json`) è il codice
della lingua (formato [ISO
639-1](https://it.wikipedia.org/wiki/Codici_lingua_ISO_639-1), es. `it`,
`en`, `es`, `fr`, `de`).

Solo l'**inglese** è incorporato direttamente nello script
(`EMBEDDED_TRANSLATIONS`) come ultima rete di sicurezza, così l'app
funziona anche se questa cartella manca del tutto. **L'italiano e tutte
le altre lingue vivono esclusivamente qui**, in `locales/*.json`: se
elimini `locales/it.json` l'app perde il supporto italiano, non c'è una
copia di riserva nel codice.

### Aggiungere una nuova lingua

1. Copia `en.json` e rinominalo con il codice della tua lingua, es.
   `pt.json` per il portoghese.
2. Traduci ogni valore (il testo tra virgolette dopo i `:`). Non
   modificare le chiavi (il testo a sinistra dei `:`).
3. Alcune frasi contengono un segnaposto `{min}` (es. `"subtitle"`):
   lascialo invariato, verrà sostituito a runtime con il numero di
   minuti scelto dall'utente.
4. Non serve modificare il codice Python: al prossimo avvio la lingua
   comparirà automaticamente nel selettore in alto a destra nella
   finestra, con il nome che hai indicato in `"lang_name"`.
5. Puoi anche inviare un file **parziale**: le chiavi mancanti
   ricadranno automaticamente sull'inglese, quindi non serve tradurre
   tutto in un'unica pull request.

### Chiavi disponibili

| Chiave | Dove compare |
|---|---|
| `lang_name` | Nome della lingua nel menu selettore (nella lingua stessa, es. "Deutsch") |
| `app_title` | Titolo della finestra |
| `header_title` | Titolo accanto all'icona occhio in alto |
| `subtitle` | Sottotitolo (usa `{min}`) |
| `duration_label` / `minutes_label` | Selettore durata |
| `status_ready` / `status_running` / `status_paused` / `status_alert` | Etichetta di stato |
| `btn_start` / `btn_pause` / `btn_reset` | Pulsanti principali |
| `footer_hint` | Suggerimento in fondo alla finestra |
| `dialog_title` / `dialog_heading` / `dialog_body` / `dialog_ok` | Popup di fine pausa |
| `notif_title` / `notif_body` | Notifica desktop di sistema |

---

## English

This folder holds the UI translations for **Timer Occhi 20-20-20** (the
20-20-20 Eye Timer). Each file is a JSON object sharing the same set of
keys; the file name (without `.json`) is the language code ([ISO
639-1](https://en.wikipedia.org/wiki/ISO_639-1), e.g. `it`, `en`, `es`,
`fr`, `de`).

Only **English** is embedded directly in the script
(`EMBEDDED_TRANSLATIONS`) as a last-resort fallback, so the app still
works if this folder is missing entirely. **Italian and every other
language live exclusively here**, in `locales/*.json` - deleting
`locales/it.json` removes Italian support, there is no backup copy in
the source code.

### Adding a new language

1. Copy `en.json` and rename it to your language code, e.g. `pt.json`
   for Portuguese.
2. Translate each value (the quoted text after each `:`). Leave the
   keys (the text to the left of `:`) unchanged.
3. Some strings contain a `{min}` placeholder (e.g. `"subtitle"`) -
   leave it as-is; it's replaced at runtime with the user's chosen
   number of minutes.
4. No Python code changes needed: on next launch, the language will
   automatically appear in the picker at the top-right of the window,
   labeled with whatever you put in `"lang_name"`.
5. Partial files are welcome too - any missing key falls back to
   English automatically, so you don't need to translate everything in
   one pull request.

### Available keys

See the table above - key names are the same regardless of language.
