# Polar Reports

Webová aplikace pro analýzu dat z **Polar Team Pro** a tvorbu reportů pro jednotlivé hráčky.
Každá hráčka vidí své statistiky a jak si stojí v porovnání s ostatními hráčkami.

## Co aplikace umí

- Nahrání exportů z Polar Team Pro (**CSV** i **JSON**, česká i anglická verze exportu). Jeden soubor = jeden trénink jedné skupiny.
- Tři typy tréninků: **Standardní trénink**, **Dovednostní trénink**, **Zápas**. Typ se odhadne z názvu souboru
  (`zapas` → Zápas, `dovednost`/`skill` → Dovednostní trénink) a dá se v aplikaci upravit, stejně jako skupina (např. Skupina A / B).
- **Individuální report** za trénink: trvání, TF, vzdálenost, zátěž, max. rychlost vs. průměr týmu,
  tepové a rychlostní zóny, paprskový graf percentilů, pořadí a slovní shrnutí.
- **Přehled hráčky za období**: průměry podle typu tréninku vs. tým, vývoj zátěže a vzdálenosti, seznam tréninků s pořadím.
- **Report skupiny** za trénink: pořadí vzdálenosti, zátěže a TF, tabulka všech hráček, porovnání percentilů.
- Export do **PDF** (jednotlivě nebo ZIP pro všechny hráčky).

### Jak se počítají percentily

V rámci jednoho tréninku/zápasu dostane každá hráčka pro každý ukazatel percentil
`pořadí / počet hráček × 100` (nejlepší = 100, shodné hodnoty sdílí vyšší pořadí).
Ukazatele: tréninková zátěž, průměrná TF %, kardio zátěž, vzdálenost/min, sprinty.
Celkový percentil je jejich průměr a určuje pořadí.

## Spuštění

```bash
pip install -r requirements.txt
streamlit run app.py
```

PDF export používá WeasyPrint, který potřebuje systémové knihovny Pango
(Linux: `apt install libpango-1.0-0 libpangoft2-1.0-0`, macOS: `brew install pango`,
Windows: viz dokumentace WeasyPrint). Pro Streamlit Community Cloud je připraven `packages.txt`.

Příkazová řádka (bez webu):

```bash
python -m polar_reports.cli exporty/*.csv --out reports/ --team "KTM - GU15"
```

## Struktura

| Soubor | Účel |
| --- | --- |
| `app.py` | webová aplikace (Streamlit) |
| `polar_reports/ingest.py` | načtení a normalizace exportů (CSV/JSON, CZ/EN sloupce) |
| `polar_reports/analysis.py` | percentily, pořadí, historie hráčky, souhrny podle typu |
| `polar_reports/charts.py` | grafy jako SVG (stejné ve webu i v PDF) |
| `polar_reports/report.py`, `templates/report.html` | stránky reportů a export do PDF |
| `tests/` | testy se smyšlenými daty ve formátu Polar exportu |

## Ochrana osobních údajů

Exporty obsahují jména a zdravotní data nezletilých hráček. **Skutečná data nenahrávejte do tohoto (veřejného) repozitáře** –
složka `data/` je v `.gitignore`. Testovací data v `tests/fixtures/` jsou smyšlená.
