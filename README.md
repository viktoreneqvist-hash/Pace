# Pace

Pace är en privat, lokal träningscoach för löpning och cykling. Den hämtar din
Garmin-historik till din egen dator, bygger ett granskningsbart kort planutkast
och använder AI bara när du uttryckligen ber om en plan eller ställer en fråga.

Detta är en tidig privat alpha för inbjudna vänner. Du behöver ett eget
Garmin-konto och, för AI-planer eller AI-frågor, en egen OpenAI API-nyckel.
Pace är inte medicinsk rådgivning och diagnostiserar inte skador eller sjukdom.

## Du behöver

- macOS eller annan dator med Python 3.14 och [`uv`](https://docs.astral.sh/uv/)
- Garmin Connect-konto
- OpenAI API-nyckel om du vill använda AI-funktionerna

På Mac med Homebrew installerar du uv en gång:

```bash
brew install uv
```

## Starta Pace

Klona det privata repo som du blivit inbjuden till:

```bash
git clone <repo-adress>
cd pace
uv sync
```

Skapa din lokala fil för OpenAI-nyckeln. Den ignoreras av Git och Pace läser
den automatiskt — du behöver aldrig köra `source` innan du använder Pace.

```bash
mkdir -p .local
cp pace.env.example .local/pace.env
chmod 600 .local/pace.env
open -e .local/pace.env
```

Klistra in din egen nyckel efter `OPENAI_API_KEY=` och spara. Hoppa över detta
om du först bara vill synka Garmin och se vanliga Python-beräknade mått.

Initiera databasen, logga in på Garmin och hämta senaste veckan:

```bash
uv run pace db init
uv run pace garmin login
uv run pace sync --days 7
uv run pace state show
```

Garmin frågar efter e-post, lösenord och eventuellt MFA direkt i terminalen.
Pace sparar bara en återanvändbar Garmin-session lokalt på din dator.

## Skapa första planen

Pace behöver 28 aktuella sammanhängande Garmin-dagar innan ett planutkast kan
skapas. Importera äldre veckor i sjudagarsbatcher om `pace plan readiness`
inte säger `ready`:

```bash
uv run pace sync --days 7 --end-date 2026-07-18
uv run pace sync --days 7 --end-date 2026-07-11
uv run pace sync --days 7 --end-date 2026-07-04
uv run pace plan readiness
```

Spara tillgänglighet och huvudsport. Det är praktiska gränser, inte påståenden
om din kapacitet:

```bash
uv run pace preferences set \
  --sport-role ride_primary \
  --day mon:any --day tue:any --day wed:any --day thu:any \
  --day fri:any --day sat:any --day sun:any
uv run pace preferences ambition --ambition balanced
```

Lägg till ett lopp när du har ett. `A` är huvudmålet, `B` är ett
sekundärt lopp med partiell taper och `C` behandlas som ett hårt träningspass:

```bash
uv run pace race add \
  --name "Exempel 10 km" \
  --sport run \
  --date 2026-10-11 \
  --distance-km 10 \
  --priority A \
  --desired-time 00:45:00
```

Skapa ett 14-dagars utkast. Planen blir inte aktiv förrän du godkänner den:

```bash
uv run pace plan draft --race-id 1 --days 14
uv run pace plan review --id 1
uv run pace plan report --id 1
open reports/plan-1.html
uv run pace plan accept --id 1
```

Byt `1` mot plan-id:t som Pace skriver ut. HTML-rapporten är privat och lokal;
den skickas inte till GitHub.

## Till vardags

```bash
uv run pace sync --days 7
uv run pace plan today
uv run pace coach ask --plan-id 1 "Kan jag cykla i stället för dagens löpning?"
uv run pace plan feedback --session-id 1 --outcome completed
```

Om ett pass missas eller blir begränsat registrerar du utfallet och skapar ett
kort revisionsutkast. Pace skriver aldrig över ett accepterat plan automatiskt.

```bash
uv run pace plan feedback --session-id 1 --outcome skipped "Jobbresa"
uv run pace plan revise --id 1 --days 7
```

## Integritet och gränser

- Databasen finns i `data/pace.db`; Garmin-token finns i `.local/`.
- De filerna, din AI-nyckel och HTML-rapporter ignoreras av Git.
- Vid en AI-fråga skickar Pace bara ett litet urval av normaliserade fakta till
  OpenAI — aldrig Garmin-lösenord, token, rådata, databasdump eller privat
  context-text.
- Python räknar mått och datakvalitet. AI:n kan skapa ett granskningsbart
  utkast, men kan inte acceptera eller skriva över ditt plan.
- Håll din egen API-nyckel privat. Du betalar själv för din OpenAI-användning.

## Om något krånglar

Kör detta innan du rapporterar ett problem:

```bash
uv run ruff check .
uv run pytest -q
uv run pace --help
```

Dela eller committa aldrig `data/`, `.local/`, `reports/` eller din lokala
nyckelfil.

## För den som vill utveckla

Pace är avsiktligt litet och lokalt. Arkitektur, beslut och roadmap finns i
`docs/`. Läs [AGENTS.md](AGENTS.md) innan du ändrar kod.

Licens: [MIT](LICENSE).
