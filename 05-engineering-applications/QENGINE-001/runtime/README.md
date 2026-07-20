# TZAR-QENGINE reference runtime

Статус: `reference-candidate` · версия `0.1.0-rc.1`.

Эталонный кандидат реализует единый контракт `QEngine(Request, Context, Policy) → EngineResult` для `QP-01`, `QR-01`, `QG-01`, `QA-01`, `QC-01` и `QI-01`.

Исполнимый модуль расположен в [`products/tzar-conductance/qengine/qengine.mjs`](../../../products/tzar-conductance/qengine/qengine.mjs), чтобы один и тот же файл использовался тестами и публичным браузерным стендом.

Запуск проверок:

```bash
node 05-engineering-applications/QENGINE-001/runtime/tests.mjs
```

Границы: runtime не выполняет криптографию, аутентификацию, авторизацию операционной системы или физическое уничтожение данных. Он принимает явные результаты внешних проверяемых механизмов и закрывает операцию при отсутствии обязательного свидетельства.
