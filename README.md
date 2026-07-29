# Pace

Pace är en privat, lokal träningscoach för löpning och cykling. Den hämtar din
Garmin-historik till din egen dator, bygger en granskningsbar kort planversion
och använder AI bara när du uttryckligen ber om en plan, fråga eller veckoreview.

Detta är en tidig privat alpha för inbjudna vänner. Du behöver ett eget
Garmin-konto och, för AI-planer eller AI-frågor, en egen OpenAI API-nyckel.
Pace är inte medicinsk rådgivning och diagnostiserar inte skador eller sjukdom.

## Så fungerar Pace

Pace delar upp jobbet mellan kod och AI så att träningsfakta inte blir en
gissning:

```text
Garmin-data → lokal databas → Python räknar fakta → du lägger till context
→ AI-coachen förklarar eller föreslår → du bekräftar varje sparad ändring
```

- **Python** räknar tid, distans, frekvens, HRV-baslinjer och datakvalitet.
- **Du** styr mål, lopp, tillgänglighet och vad som faktiskt hände på ett pass.
- **AI-coachen** diskuterar och föreslår. Ditt klick på **Skapa plan** är det
  enda godkännandet av en ny plan: Pace aktiverar den först efter full Python-
  validering. Coachen kan aldrig själv starta det flödet, spara feedback eller
  ändra en plan.
- **Allt kör lokalt.** Garmin-token, databas, rapporter och API-nyckel lämnar
  inte datorn via Git.

## Du behöver

- macOS eller annan dator med Python 3.14 och [`uv`](https://docs.astral.sh/uv/)
- Garmin Connect-konto
- OpenAI API-nyckel om du vill använda AI-funktionerna

På Mac med Homebrew installerar du uv en gång:

```bash
brew install uv
```

## Starta Pace — utan terminal efter installation

Klona det privata repo som du blivit inbjuden till:

```bash
git clone <repo-adress>
cd Pace
uv sync
```

Dubbelklicka sedan på **Start Pace.command** i Finder. Första gången öppnar Pace
din webbläsare och guidar dig genom allt som behövs:

- din OpenAI API-nyckel (lokalt och privat)
- Garmin-inloggning, inklusive eventuell MFA
- träningsläge, ambitionsläge och vilka dagar du är tillgänglig
- Garmin-pulszoner om du tillåter cykling
- tolv säkra Garmin-batcher för 80 dagars historik
- valfria framtida lopp och sedan ett uttryckligt planmål

Databasen initieras automatiskt vid start. Garmin-lösenordet sparas aldrig;
Pace sparar bara Garmins återanvändbara lokala session. När en plan är
skapad går Pace över till den vanliga Coach-vyn. Du kan göra allt vardagligt i
webbgränssnittet; terminalkommandona längre ned är för felsökning och avancerad
användning.

## Öppna den lokala coachen

Till vardags räcker det att dubbelklicka på **Start Pace.command**. Alternativt
kan du starta från terminalen:

```bash
uv run pace serve
```

Webbläsaren öppnas automatiskt på `http://127.0.0.1:8765`. Sidan kör bara på
din egen dator och är inte publicerad på internet. Låt terminalfönstret vara
öppet medan du använder Pace; stoppa den lokala sidan med `Ctrl+C` när du är
klar.

I sidan kan du läsa den aktiva planen, inställningar, kommande lopp och aktuella
Pace-fakta samt prata med coachen. Den övre navigeringen håller dig i samma
lokala app:

- **Coach** är samtalet och platsen där du kan bekräfta context och passutfall.
- **Dashboard** visar aktuella tränings- och recovery-fakta. Den räknas om från
  dina lokala data varje gång du öppnar den.
- **Plan** visar den aktiva plan som gäller i dag och uppdateras när du
  har sparat feedback.
- **Veckoreview** visar den senaste uttryckliga AI-snapshoten. Den skrivs inte
  om automatiskt när ny feedback tillkommer, så en gammal vecka får samma
  bedömning när du läser den igen.
- **Inställningar** ändrar träningsläge, ambition, tillgängliga dagar,
  cykelpulszoner och framtida lopp. Du kan också synka de senaste sju eller
  80 dagarna därifrån. Ändringen används först i nästa plan; en aktiv plan
  skrivs aldrig om.

Pace ändrar aldrig en aktiv plan automatiskt och chattens korta historik
försvinner när den lokala servern stoppas.

### Kommandon direkt i chatten

Skriv ett snedstreck i coachens chattruta för att använda ett säkert Pace-
kommando. De här kommandona kör **inte** AI:

```text
/help
/today
/state
/analysis
```

- `/help` visar kommandolistan.
- `/today` visar dagens, eller nästa, planerade pass.
- `/state` visar kort Pace-status: aktiv plan och detaljfönster.
- `/analysis` visar träningsfakta för de senaste 28 dagarna.

Två kommandon kan göra ett externt anrop. De startar därför aldrig direkt, utan
visar först ett tydligt bekräftelsekort:

```text
/sync
/review weekly
```

- `/sync` förbereder en Garmin-synk av de senaste sju kalenderdagarna. Klicka
  **Starta synk** för att faktiskt hämta data.
- `/review weekly` förbereder en ny AI-veckoreview. Klicka **Skapa
  veckoreview** först när du vill göra OpenAI-anropet.

Chatten kan inte köra fria terminalkommandon. Det betyder att text som
`uv run pace ...`, filer och andra systemkommandon aldrig kan köras av misstag
från webbläsaren.

## Uppdatera Pace

När du hämtar en ny version, kör detta en gång innan du använder Pace. Det
uppdaterar bara den lokala databasstrukturen; Garmin-data och planer raderas
inte.

```bash
git pull
uv sync
uv run pace db init
```

## Skapa första planen

Första-startflödet ovan är den rekommenderade vägen. Det visar samma steg i
webbläsaren och behöver inga kommandon efter `uv sync`.

Pace behöver 28 aktuella sammanhängande Garmin-dagar innan en plan kan
skapas. Första-starten och Inställningar importerar normalt 80 dagar, vilket
ger coachen ett bättre historiskt underlag. Varje Garmin-anrop är ändå högst
sju dagar. Importera äldre veckor manuellt i sjudagarsbatcher om `pace plan
readiness` inte säger `ready`:

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

Sportlägena är `run_only`, `run_primary`, `balanced`, `ride_primary` och
`ride_only`. `run_only` och `ride_only` är hårda gränser: Pace föreslår aldrig
det andra sportslaget. De två *primary*-lägena är bara din preferens; modellen
väljer fortfarande passen utifrån fakta, återhämtning och planmålet.

Lägg till ett lopp när du har ett. `A` är huvudmålet, `B` är ett
sekundärt lopp med partiell taper och `C` behandlas som ett hårt träningspass:

```bash
uv run pace race add "Exempel 10 km" \
  --sport run \
  --date 2026-10-11 \
  --distance-km 10 \
  --priority A \
  --desired-time 00:45:00
```

Skapa en 14-dagars plan. Kommandot, precis som knappen i Coach, är ditt
uttryckliga godkännande. Pace validerar först hela AI-svaret och aktiverar
sedan planen. Om valideringen eller AI-anropet misslyckas ligger den tidigare
aktiva planen kvar oförändrad:

```bash
uv run pace plan draft --race-id 1 --days 14
uv run pace plan review --id 1
uv run pace plan report --id 1
open reports/plan-1.html
```

Byt `1` mot plan-id:t som Pace skriver ut. HTML-rapporten är privat och lokal;
den skickas inte till GitHub.

En ny plan innehåller ett faktiskt passupplägg, inte bara en rubrik:
uppvärmning, jämna delar, intervallrepetitioner med vila och nedjogg. Pace kan
alltså uttrycka exempelvis `10 × 1 km` eller `20 × 400 m` när din aktuella
fakta- och kapacitetsgrund tillåter det. Löpfart kräver fortfarande aktuell
verifierad löpevidens; annars använder planen RPE. Cykling använder aldrig
fartmål.

Ett A-lopp styr riktningen för blocket. Ett aktivt 10 km-lopp, som
Hässelbyloppet, får därför modellen att välja 10 km-relevant lokal
coachingkunskap när den skapar nästa plan. Det är inte en färdig mall: Pace
väljer fortfarande löpfrekvens, dagplacering och kvalitet från faktisk
löpkontinuitet, återhämtning och feedback. Python kräver alltså inte varannan
träningsdag eller en bestämd träningsvecka.

Ett lopp är aldrig ett tvång. Välj ett specifikt aktivt lopp, oavsett om det
har prioritet A, B eller C, när du vill att blocket ska förbereda för just det:

```bash
uv run pace plan draft --race-id 2 --days 14
```

Utelämna `--race-id` när du uttryckligen vill ha en generell plan. Då används
inga sparade lopp som planmål, även om de ligger inom de närmaste 14 dagarna:

```bash
uv run pace plan draft --days 14
```

I Coach-UI:t finns samma val under **Kommande lopp**. Välj antingen **Skapa
plan utan lopp** eller **Planera mot detta lopp**. Pace visar alltid ett
bekräftelsekort före AI-anropet. Klicket **Skapa och aktivera plan** skapar
den nya aktiva versionen först när hela planen är validerad.

## Till vardags

Det enklaste vardagsflödet är att starta den lokala appen, synka genom
`/sync`, läsa Dashboard och rapportera passutfall med vanlig svenska i Coach.
Terminalkommandona nedan finns kvar när du vill ha full kontroll, importera
historik eller felsöka.

```bash
uv run pace sync --days 7
uv run pace plan today
uv run pace plan checkpoint
uv run pace coach ask --plan-id 1 "Kan jag cykla i stället för dagens löpning?"
uv run pace plan feedback --session-id 1 --outcome completed
uv run pace plan feedback --session-id 1 --outcome completed --rpe 6
uv run pace performance sync --days 7
uv run pace plan workout evaluate --session-id 1
uv run pace trends show
uv run pace analysis show
uv run pace home
open reports/home.html
uv run pace review weekly
open reports/weekly-review.html
```

Du kan använda `uv run pace serve` i stället för merparten av de här
vardagskommandona. Terminalkommandona finns kvar för import, felsökning och
fullt reproducerbara arbetsflöden.

`pace home` bygger om den lokala dashboarden och den aktiva planrapporten och
samlar dem på en startsida. Där visas även aktuellt ambitionsläge, sportroll,
veckotillgänglighet och sparade cykelpulszoner. Den synkar inte Garmin, anropar
inte AI och ändrar inte planen. `pace plan checkpoint` säger när detaljfönstret
håller på att ta slut eller ett lopp närmar sig. Den visar bara vilken ny plan
eller revision du kan skapa; den startar aldrig en AI-körning själv.

Om ett pass missas eller blir begränsat registrerar du utfallet och skapar en
kort revision. Ditt revisionskommando är ett uttryckligt beslut; en lyckat
validerad revision blir aktiv och den tidigare versionen arkiveras lokalt.

```bash
uv run pace plan feedback --session-id 1 --outcome skipped --reason schedule --note "Jobbresa"
uv run pace plan revise --id 1 --days 7
```

`pace performance sync` hämtar integritetsminimerade Garmin-detaljer och splits
för redan synkade löp- och cykelpass. `pace plan workout evaluate` jämför sedan
planerad tid, distans och intervallstruktur med dessa data. Splits är fortfarande
inte ett bevis på att varje intervall utfördes rätt; din registrerade feedback
är det enda uttryckliga utfallet och det som kan ligga till grund för nästa
revision.

`pace analysis show` visar de faktiska 28-dagarsvärdena för tid, distans,
frekvens, feedback/RPE och recovery-täckning. Pace skapar inget eget dolt
belastningsscore. Saknad distans visas som saknad, inte som noll.

Om en plan innehåller en coachprincip du vill behålla kan du bekräfta
den. Den granskas igen efter 84 dagar och ändrar aldrig en plan automatiskt:

```bash
uv run pace profile accept --plan-id 1 --principle-index 0
uv run pace profile list
```

## Integritet och gränser

- Databasen finns i `data/pace.db`; Garmin-token finns i `.local/`.
- De filerna, din AI-nyckel och HTML-rapporter ignoreras av Git.
- Vid en AI-fråga skickar Pace bara ett litet urval av normaliserade fakta till
  OpenAI — aldrig Garmin-lösenord, token, rådata, databasdump eller privat
  context-text.
- Python räknar mått och datakvalitet. AI:n kan föreslå en granskningsbar plan,
  men kan inte acceptera, skapa eller skriva över något utan ditt uttryckliga
  plan- eller revisionsklick.
- Pace-fakta beskriver dig och din träning. AI:n får använda allmän
  tränarkunskap för sin bedömning, men den visas som coachbedömning — inte som
  ny Pace-data eller forskning.
- Den lokala kunskapsbasen är ett granskat, källhänvisat stöd för vanliga
  uthållighetsfrågor. Den laddas från repot, söks inte på webben vid körning
  och begränsar inte AI:ns allmänna coachkunskap eller Paces faktagränser.
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

Den nätverksfria testsuiten kör även sex syntetiska coachscenarier. Du kan läsa
scenariokatalogen utan API-anrop:

```bash
uv run pace eval scenarios
```

Ett riktigt modelltest är separat och kostar sex syntetiska OpenAI-anrop. Det
använder ingen riktig Garmin- eller atletdata och körs aldrig automatiskt:

```bash
uv run pace eval coach --live
```

Licens: [MIT](LICENSE).
