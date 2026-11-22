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

### S kým se hráčka porovnává

Ve výchozím nastavení se hráčka porovnává se **všemi hráčkami, které měly stejný typ tréninku ve stejný den**
(obě skupiny → 40 hráček). Pořadí, percentily i „průměr týmu“ se počítají z tohoto bloku.
V aplikaci lze přepnout na porovnání jen s vlastní skupinou. Typ tréninku (Standardní / Dovednostní / Zápas)
se vybírá nahoře v aplikaci a podle něj se tvoří reporty i hromadný export.

### Jak se počítají percentily

V rámci porovnávaného bloku dostane každá hráčka pro každý ukazatel percentil
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

### Online pro trenéry (Streamlit Community Cloud)

1. Na [share.streamlit.io](https://share.streamlit.io) se přihlaste přes GitHub a zvolte *Create app* → tento repozitář, soubor `app.py`.
2. V *Advanced settings → Secrets* nastavte heslo:
   ```toml
   APP_PASSWORD = "zvolte-silne-heslo"
   ```
3. Odkaz a heslo dejte jen trenérům. Data se do aplikace jen nahrávají a nikde se neukládají.

Bez nastaveného `APP_PASSWORD` aplikace heslo nevyžaduje (vhodné pro spuštění na vlastním počítači).

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
