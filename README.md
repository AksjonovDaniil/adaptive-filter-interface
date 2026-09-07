# adaptive-filter-interface

Studiju projekts kursam **Lietotāja adaptīvā interfeisa programmatūra**.

## Projekta tēma

**Adaptīvs filtru interfeiss datu tabulai**

## Autors

Daniils Aksjonovs

## Apraksts

Projekta mērķis ir izveidot adaptīvu filtru interfeisu datu tabulai.

Lietotājs varēs ievadīt filtrus, piemēram:

`statuss = "Atvērts" UN prioritāte = "Augsta"`

Sistēma analizēs lietotāja filtru izmantošanas vēsturi un biežāk izmantotos filtrus piedāvās kā ātri pieejamus šablonus.

Projektā tiks realizēta filtru sintaktiskā un semantiskā pārbaude, lietotāja modeļa veidošana un interfeisa adaptācija.

## Tehnoloģijas

- PHP 8.3
- Laravel
- Blade
- SQLite
- Git / GitHub

## Projekta struktūra

- `docs/` — projekta dokumentācija
- `src/lexer/` — leksiskā analīze
- `src/parser/` — sintaktiskā analīze
- `src/semantics/` — semantiskā analīze
- `src/ir/` — starpkods
- `src/ui/` — lietotāja interfeiss
- `src/adaptation/` — adaptācijas modulis
- `tests/` — testi

## Palaišana

Projekta realizācija vēl nav uzsākta. Palaišanas instrukcija tiks papildināta projekta izstrādes laikā.
