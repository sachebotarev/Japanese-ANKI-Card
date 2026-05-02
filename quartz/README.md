# Quartz (сайт по заметкам)

Статический сайт из папки **`Записи/`** в корне репозитория. Сборка и публикация — см. [docs/quartz-site.md](../docs/quartz-site.md).

Кратко:

```bash
cd ..
python3 scripts/sync_quartz_content.py
cd quartz
npm ci
npx quartz build --serve
```

Требуется **Node 22+**.
