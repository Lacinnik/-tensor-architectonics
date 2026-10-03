# -tensor-architectonics · научный канон ТзАр

Корпус по уровням: `01-declarations` → `02-axioms` → `03-theory` → `04-mathematical-apparatus` → `05-engineering-applications`; карта — `contour/manifest.json`, термины — `GLOSSARY.md`. Продукты — `products/tzar-conductance/` (публикуется на Pages целиком: Conductance, `ego-interface/`, `qengine/`, `supra-cosmos/`).

## Перед отправкой

```bash
node products/tzar-conductance/tests.mjs
node products/tzar-conductance/ego-interface/tests.mjs
node products/tzar-conductance/supra-cosmos/tests.mjs
node 05-engineering-applications/QENGINE-001/runtime/tests.mjs
node --test 05-engineering-applications/QENGINE-001/runtime/fail-closed.test.mjs
node 05-engineering-applications/EXPERIMENT-001/verify.mjs
python -m unittest discover -s tools/eagc012 -p 'test_*.py'   # при изменениях tools/eagc012
```

package.json нет; workflow запускаются по путям.

## Ловушки

- **Канонические документы** (`status: canonical` во front matter) не менять по смыслу: правки формулировок — только по решению автора. Новый конструкт получает собственный идентификатор (`TZAR-…-00N`) и статус `candidate`.
- **`GLOSSARY.md`** — только дословные цитаты с ссылкой на раздел; при изменении канона обновить цитату.
- **EAGC-012** (`tools/eagc012`): замороженные предсказания и протоколы в `frozen/` не перезаписывать — это предрегистрация.
- **Supra Cosmos**: при изменении сменить `CACHE` в `products/tzar-conductance/supra-cosmos/sw.js`.
- **Авторские ключи** (`products/tzar-conductance/author-keys/`) — открытая часть; приватных ключей в репозитории быть не должно.
- Цитирование: `CITATION.cff`, `.zenodo.json` (DOI выдаётся Zenodo при релизе).

## Экосистема

Четыре репозитория одного автора (Lacinnik): `architectonica-az-buki` (корпус и исходные ядра), `-tensor-architectonics` (научный канон ТзАр), `reason-` (лаборатория РЕЗОН), `Game-GDEYA` (игра и Platform 2.0 — единая точка входа). Все сайты — статические GitHub Pages, всё работает локально в браузере.

## Правила содержания

- Статусы (`canonical`, `stable`, `candidate`, `not-accepted`…) присваивает только автор. Не повышать статус по итогам CI или собственной проверки; в `ecosystem.status.json` у каждого статуса поле `source` указывает документ автора, а неуказанный статус — `unstated`.
- `Q` остаётся `null`, пока отклик не наблюдён; игровой балл — `Qsim`. Не выдавать симуляцию за наблюдение или диагностику.
- TZAR-LANGUAGE-001 — детерминированный символический компилятор, не обученная нейросеть. Не писать иного.
- Термины корпуса брать из канонических документов (`-tensor-architectonics/GLOSSARY.md`), не пересказывать своими определениями.
- Тексты и интерфейс — на русском; английский — только `README.en.md`.
- Ссылки в Markdown проверяет workflow `links.yml` (lychee): в PR — внутренние, еженедельно — внешние.
