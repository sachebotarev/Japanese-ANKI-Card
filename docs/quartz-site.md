# Сайт Quartz на GitHub Pages

В репозитории каталог **`quartz/`** — это [Quartz v4](https://quartz.jzhao.xyz/). В GitHub Pages попадает только **собранный** статик (`quartz/public/`); исходники заметок по-прежнему в **`Записи/`** в корне репозитория.

## Как устроено

1. **`scripts/sync_quartz_content.py`** копирует `Записи/` → `quartz/content/Записи/` и заменяет вставки `![[Картинки/...]]` и `![[Произношение/...]]` на URL **raw.githubusercontent.com** (картинки — `![](...)`, mp3 — `<audio controls>`). Локальные `Картинки/` и `Произношение/` в сайт **не копируются**.

2. **`quartz/quartz.config.ts`**: заголовок, `locale: ru-RU`, `baseUrl` для project Pages — `sachebotarev.github.io/Japanese-ANKI-Card` (при смене владельца/имени репозитория обновите).

3. **GitHub Actions**: `.github/workflows/quartz-pages.yml` — при push в `main` (изменения в `Записи/`, `quartz/`, скрипте или workflow) или вручную (**Actions → Quartz GitHub Pages → Run workflow**). Для публикации используются `actions/upload-pages-artifact@v5` и `actions/deploy-pages@v5` (runtime Node 24, без предупреждений о deprecated Node 20).

## Первый запуск на GitHub

1. **Settings → Pages → Source**: выберите **GitHub Actions** (не «Deploy from branch»).

2. Закоммитьте и запушьте изменения; дождитесь зелёного workflow.

3. Сайт: `https://sachebotarev.github.io/Japanese-ANKI-Card/` (или ваш `https://<user>.github.io/<repo>/`).

Если в **Settings → Environments** уже есть окружение `github-pages` со старыми правилами и деплой падает — удалите его, как советует [документация Quartz](https://quartz.jzhao.xyz/hosting); Actions создаст заново.

## Локальная сборка

Нужны **Node ≥ 22** и **npm ≥ 10.9** (см. `quartz/package.json` → `engines`).

```bash
cd "/path/to/Japanese ANKI Card"
python3 scripts/sync_quartz_content.py   # опционально: QUARTZ_RAW_BASE=https://raw.githubusercontent.com/OWNER/REPO/main
cd quartz
npm ci
npx quartz build --serve
```

Папки `quartz/content/`, `quartz/public/`, `quartz/node_modules/` в git **не коммитятся** (см. `.gitignore`).

### Почему на главной не должен отображаться RSS

Папка `quartz/content/` в `.gitignore`, чтобы не коммитить копию `Записи/`. В upstream Quartz glob файлов контента использует `gitignore: true`, из‑за чего **все** `.md` внутри игнорируемой папки выпадают из сборки: не появляется `index.html`, в корне остаётся только `index.xml` (RSS), и браузер может показать XML как «главную страницу». В этом репозитории в `quartz/quartz/util/glob.ts` задано **`gitignore: false`** только для такого сценария (подкаталоги `content/` без лишнего мусора).

## Переменная `QUARTZ_RAW_BASE`

По умолчанию скрипт берёт `origin` из git и ветку **`main`**. В CI задаётся автоматически из `github.repository` и `github.ref_name`. Для превью с другой ветки:

`QUARTZ_RAW_BASE=https://raw.githubusercontent.com/OWNER/REPO/branch-name python3 scripts/sync_quartz_content.py`

**Важно:** raw-ссылки работают для **публичного** репозитория; иначе медиа с сайта не откроются без авторизации.
