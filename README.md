# unubot

A community support bot for the [UNU Community Discord](https://discord.gg/) — help with unu Scooter Pro and [LibreScoot](https://github.com/librescoot). German-first, English supported.

## What it does

- **`/faq <thema>`** — canned answers to the questions that keep coming up (AUX battery, app connectivity, firmware versions, spare parts, DC-converter safety, LibreScoot intro, …).
- **`/glossar <begriff>`** — glossary of the tech acronyms people trip over (MDB, DBC, ECU, CBB, AUX, keycard, Redis, hibernate, LibreScoot).
- **`/diagnose <flow>`** — button-driven troubleshooters. Two to start: AUX battery and app connection.
- **Welcome DM** on join with channel guide and bot pointers.
- **`/reload`** (owner-only) — re-read YAML content without restarting.

All content lives as YAML/Markdown in [`content/`](content/) so it can be edited via PR.

## Quick start

### 1. Create a Discord application

1. Go to <https://discord.com/developers/applications> → **New Application**.
2. Name it (e.g. `unubot`) and create.
3. Left sidebar → **Bot** → **Reset Token**, copy the token. This goes into `DISCORD_TOKEN` in your `.env`. **Don't commit it.**
4. Same page → **Privileged Gateway Intents** → enable **Server Members Intent** (needed for join events). Save.
5. Left sidebar → **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Bot permissions: `Send Messages`, `Embed Links`, `Read Message History`, `Use Slash Commands`
   - Copy the generated URL and open it in a browser to invite the bot to the UNU Community server.

### 2. Local development

```bash
cp .env.example .env
# fill in DISCORD_TOKEN and optionally DEV_GUILD_ID, OWNER_IDS

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

python -m unubot
```

Setting `DEV_GUILD_ID` to your test server's ID syncs commands instantly to that guild; leaving it empty syncs globally (which can take up to an hour to propagate on first use).

### 3. Run tests

```bash
pytest
```

Tests validate that all YAML content parses, has German titles/bodies, and that every `goto` in a diagnose flow points to a defined step.

### 4. Deploy with Docker

```bash
docker compose up -d --build
docker compose logs -f unubot
```

The `content/` directory is mounted read-only so you can edit YAML on disk and run `/reload` to pick it up without rebuilding the image.

## Configuration

All via environment variables (or a `.env` file next to the bot):

| Variable | Purpose |
|---|---|
| `DISCORD_TOKEN` | Bot token from the Developer Portal. **Required.** |
| `OWNER_IDS` | Comma-separated Discord user IDs allowed to run `/reload`. |
| `DEV_GUILD_ID` | Restrict slash-command registration to one guild (instant sync). Empty = global. |
| `WELCOME_FALLBACK_CHANNEL_ID` | Post welcome there if a member has DMs closed. Empty = silent fallback. |
| `LOG_LEVEL` | `DEBUG` / `INFO` / `WARNING` / `ERROR`. Default `INFO`. |

## Adding content

### FAQ or glossary entry

Create `content/faq/<slug>.yaml` (or `content/glossary/<slug>.yaml`):

```yaml
id: my-entry
aliases: [mein-eintrag, alt-name]
title:
  de: "Deutscher Titel"
  en: "English title"
body:
  de: |
    Markdown-Body auf Deutsch.
  en: |
    English markdown body.
links:
  - url: https://example.com
    label:
      de: "Label"
      en: "Label"
tags: [battery, hardware]
```

- `aliases` are matched alongside the ID for lookup and autocomplete.
- English is optional; if missing, German is shown for English users too.
- `tags` tint the embed (`librescoot` → purple, anything else → unu red).

### Diagnose flow

`content/diagnose/<slug>.yaml`:

```yaml
id: myflow
title:
  de: "Titel"
  en: "Title"
start: first-step

steps:
  first-step:
    prompt:
      de: "Frage?"
      en: "Question?"
    choices:
      - label: { de: "Ja", en: "Yes" }
        goto: yes-step
      - label: { de: "Nein", en: "No" }
        goto: terminal
  yes-step:
    prompt: { de: "Und weiter?", en: "And then?" }
    choices:
      - label: { de: "Ende", en: "Done" }
        goto: terminal
  terminal:
    answer:
      de: "Antwort."
      en: "Answer."
```

Steps with `answer:` and no `choices:` are terminal. Tests will fail if any `goto` references an undefined step.

### Welcome text

`content/welcome/de.md` and `content/welcome/en.md` — plain markdown, sent as a DM to new members. Keep it short; Discord DM embeds are a pain.

## Project layout

```
src/unubot/
  __main__.py        # entry point
  bot.py             # UnuBot (commands.Bot subclass), cog loader, tree sync
  config.py          # env config
  i18n.py            # locale detection (DE default), UI string table
  content.py         # YAML loader + fuzzy lookup
  embeds.py          # shared embed rendering
  cogs/
    faq.py           # /faq with autocomplete
    glossary.py      # /glossar with autocomplete
    diagnose.py      # /diagnose with button-driven flows
    welcome.py       # on_member_join DM
    admin.py         # /reload
content/
  faq/*.yaml
  glossary/*.yaml
  diagnose/*.yaml
  welcome/{de,en}.md
tests/
  test_content.py    # YAML validation, lookup correctness
  test_i18n.py       # locale detection, string interpolation
```

## Roadmap / not yet built

- Keyword-triggered auto-responder (mod opt-in per channel)
- RAG over `tech-reference/` for open-ended questions
- Moderation helpers (thread-from-message, close-resolved)
- More diagnose flows (CBB, dashboard, motor fault codes)

## License

MIT.
