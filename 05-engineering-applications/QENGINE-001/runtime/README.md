# TZAR-QENGINE reference runtime

Статус: `reference-candidate` · версия `0.1.0-rc.1`.

Эталонный кандидат реализует единый контракт `QEngine(Request, Context, Policy) → EngineResult` для `QP-01`, `QR-01`, `QG-01`, `QA-01`, `QC-01` и `QI-01`.

Публичный стенд: https://lacinnik.github.io/-tensor-architectonics/qengine/

Исполнимый модуль расположен в [`products/tzar-conductance/qengine/qengine.mjs`](../../../products/tzar-conductance/qengine/qengine.mjs), чтобы один и тот же файл использовался тестами и публичным браузерным стендом.

Запуск проверок:

```bash
node 05-engineering-applications/QENGINE-001/runtime/tests.mjs
```

Ожидаемый результат: `TZAR-QENGINE reference candidate: 35 assertions passed.`

Границы: runtime не выполняет криптографию, аутентификацию, авторизацию операционной системы или физическое уничтожение данных. Он принимает явные результаты внешних проверяемых механизмов и закрывает операцию при отсутствии обязательного свидетельства.
