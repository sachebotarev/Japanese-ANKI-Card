# Сайт Quartz на GitHub Pages

Сайт собирается **ванильным [Quartz v4](https://quartz.jzhao.xyz/)** — апстрим клонируется на сборку, никакой форк в репозитории не лежит. Наши настройки и кастомизации живут в **`quartz_overlay/`** и копируются поверх клона.

## Как устроено

1. **`quartz_overlay/`** — единственное «наше» в Quartz‑части репозитория:
   - `quartz_overlay/quartz.config.ts` — конфигурация сайта (заголовок, `locale: ru-RU`, `baseUrl` для project Pages — `sachebotarev.github.io/Japanese-ANKI-Card`).
   - `quartz_overlay/quartz.layout.ts` — layout: проводник с `mapFn` (имя темы из пути, не из `title` в `contentIndex.json`), список тегов, `MyGraph` вместо стандартного `Component.Graph`.
   - `quartz_overlay/quartz/components/custom/MyGraph.tsx` — обёртка над штатным `Component.Graph`, подменяющая inline‑скрипт.
   - `quartz_overlay/quartz/components/custom/scripts/myGraph.inline.ts` — копия `graph.inline.ts` с двумя точечными правками: `pixi.preference: "webgl"` (у части браузеров WebGPU «вешает» первый кадр) и старт `renderLocalGraph` через `requestIdleCallback`, чтобы навигация SPA не казалась «зависшей». Полный граф открывается иконкой у блока графа или **Ctrl+G** / **⌘+G**.

2. **`scripts/sync_quartz_content.py`** — копирует `Записи/` → `quartz_content/Записи/` и заменяет вставки `![[Картинки/...]]` и `![[Произношение/...]]` на URL **raw.githubusercontent.com** (картинки — `![](...)`, mp3 — `<audio controls>`). Локальные `Картинки/` и `Произношение/` в сайт **не копируются**. Ссылки на темы с пробелами в имени папки приводятся к тем же slug, что и у Quartz (пробелы → `-`, как в `quartz/util/path.ts`). Текст карточек в `Записи/` задаётся [zapisi-spec.md](zapisi-spec.md): в разделе примеров на сайте **нет** японской строки с пропусками `_____` (она только в JSON для Anki).

3. **Ключ тегов в frontmatter — `tags:`** (английский), как и ожидает ванильный Quartz. Все элементы массива `Теги` из JSON карточки (в том числе тег урока Minna вида `みんな初級I-第03課`, см. [cards-spec.md](cards-spec.md)) уходят на сайт и по ним можно отбирать страницы. Каталог тегов — `https://<...>/tags/`.

4. **Граф в сайдбаре** («локальный»): рёбра только из **markdown‑ссылок** в `.md`; скрипт `sync_quartz_content.py` создаёт `Записи/<тема>/index.md` со списком карточек и ссылку с карточки на `index` темы. Глубина **`localGraph.depth: 2`**. Рендер графа **не блокирует** навигацию (см. `MyGraph` выше).

5. **Версия Quartz** — фиксируется в `scripts/build_quartz.sh` и в workflow переменной **`QUARTZ_VERSION`** (по умолчанию `v4.5.2`). Чтобы попробовать другой релиз/коммит — переопределите её при запуске.

6. **GitHub Actions**: `.github/workflows/quartz-pages.yml` — при push в `main` (изменения в `Записи/`, `quartz_overlay/`, `scripts/sync_quartz_content.py`, `scripts/build_quartz.sh` или сам workflow) или вручную (**Actions → Quartz GitHub Pages → Run workflow**). На этапе сборки клонируется апстрим Quartz в `.quartz-build/`, поверх копируется `quartz_overlay/`, готовится `quartz_content/`, выполняется `npx quartz build -d ../quartz_content -o ../quartz_site`. Артефакт — `quartz_site/`, отгружается через `actions/upload-pages-artifact@v5` и `actions/deploy-pages@v5`.

## Первый запуск на GitHub

1. **Settings → Pages → Source**: выберите **GitHub Actions** (не «Deploy from branch»).

2. Закоммитьте и запушьте изменения; дождитесь зелёного workflow.

3. Сайт: `https://sachebotarev.github.io/Japanese-ANKI-Card/` (или ваш `https://<user>.github.io/<repo>/`).

Если в **Settings → Environments** уже есть окружение `github-pages` со старыми правилами и деплой падает — удалите его, как советует [документация Quartz](https://quartz.jzhao.xyz/hosting); Actions создаст заново.

## Локальная сборка

Нужны **Node ≥ 22** и **npm ≥ 10.9** (требование апстрима Quartz, см. его `package.json` → `engines`).

```bash
cd "/path/to/Japanese ANKI Card"
scripts/build_quartz.sh           # обычная сборка → quartz_site/
scripts/build_quartz.sh --serve   # dev-сервер на http://localhost:8080
```

Скрипт сам клонирует апстрим в `.quartz-build/`, накатывает `quartz_overlay/`, прогоняет `sync_quartz_content.py` и собирает сайт. Каталоги `.quartz-build/`, `quartz_content/`, `quartz_site/` в git **не коммитятся** (см. `.gitignore`).

Альтернативные значения версии или репозитория:

```bash
QUARTZ_VERSION=main scripts/build_quartz.sh
QUARTZ_REPO=https://github.com/<fork>/quartz.git QUARTZ_VERSION=<branch> scripts/build_quartz.sh
```

## Переменная `QUARTZ_RAW_BASE`

По умолчанию `sync_quartz_content.py` берёт `origin` из git и ветку **`main`**. В CI задаётся автоматически из `github.repository` и `github.ref_name`. Для превью с другой ветки:

`QUARTZ_RAW_BASE=https://raw.githubusercontent.com/OWNER/REPO/branch-name python3 scripts/sync_quartz_content.py`

**Важно:** raw‑ссылки работают для **публичного** репозитория; иначе медиа с сайта не откроются без авторизации.
