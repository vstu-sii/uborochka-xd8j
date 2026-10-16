import type { AactConfig } from "aact";

// Конфиг aact для «Уборочки». Источник архитектуры — C4-диаграмма
// контейнеров (docs/architecture/container.puml); контекстная диаграмма
// (context.puml) и ERD (erd.puml) не проверяются aact — они описательные.
//
// Обоснование включённых правил и цена решения — в
// docs/adr/0001-acl-adapters-and-repository-pattern.md.
//
// Проверка: npx aact check  (0 violations на момент лабы 2)

const config: AactConfig = {
  source: {
    type: "plantuml",
    path: "./docs/architecture/container.puml",
  },

  rules: {
    acl: true, // Только ACL-контейнеры (Telegram Adapter, Vision Client) зовут внешние системы
    acyclic: true, // Граф контейнеров — DAG, без циклов
    apiGateway: true, // Каждый вызов внешней системы явно маршрутизирован через Gateway
    crud: true, // БД трогает только Assessments Repo
    dbPerService: true, // У Assessments DB один владелец-аксессор
    cohesion: true, // Связность внутри границы "Уборочка" выше, чем связи наружу
    commonReuse: true, // Реюз внешнего API — весь публичный контракт или ничего
  },
};

export default config;
