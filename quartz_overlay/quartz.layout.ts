import { PageLayout, SharedLayout } from "./quartz/cfg"
import * as Component from "./quartz/components"
import MyGraph from "./quartz/components/custom/MyGraph"
import type { FileTrieNode } from "./quartz/util/fileTrie"

/** Имя темы в проводнике из пути (не из title в JSON — надёжнее при кэше CDN/браузера). */
function explorerThemeFolderTitle(node: FileTrieNode) {
  const fp = node.data?.filePath
  if (typeof fp !== "string") return
  // После миграции тем на верхний уровень URL (`/Глаголы/`, `/Кандзи/`...)
  // берём подпись темы из пути `<тема>/index.md`.
  const m = fp.match(/^([^/]+)\/index\.md$/)
  if (m) node.displayName = m[1]
}

// components shared across all pages
export const sharedPageComponents: SharedLayout = {
  head: Component.Head(),
  header: [],
  afterBody: [],
  footer: Component.Footer({
    links: {
      GitHub: "https://github.com/sachebotarev/Japanese-ANKI-Card",
    },
  }),
}

// components for pages that display a single page (e.g. a single note)
export const defaultContentPageLayout: PageLayout = {
  beforeBody: [
    Component.ConditionalRender({
      component: Component.Breadcrumbs(),
      condition: (page) => page.fileData.slug !== "index",
    }),
    Component.ArticleTitle(),
    Component.ContentMeta(),
    Component.TagList(),
  ],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
        { Component: Component.ReaderMode() },
      ],
    }),
    Component.Explorer({
      title: "Проводник",
      // Служебный каталог "Темы" дублирует список разделов и путает пользователя.
      filterFn: (node) => node.slugSegment !== "tags" && node.slugSegment !== "Темы",
      mapFn: explorerThemeFolderTitle,
    }),
  ],
  right: [
    // Глубина 2 — меньше узлов при первом рендере (см. отложенный init графа в MyGraph).
    MyGraph({
      // Для ученика полезнее видеть связи между словами, а не шум от тегов.
      localGraph: { depth: 2, showTags: false },
    }),
    Component.DesktopOnly(Component.TableOfContents()),
  ],
}

// components for pages that display lists of pages  (e.g. tags or folders)
export const defaultListPageLayout: PageLayout = {
  beforeBody: [Component.Breadcrumbs(), Component.ArticleTitle(), Component.ContentMeta()],
  left: [
    Component.PageTitle(),
    Component.MobileOnly(Component.Spacer()),
    Component.Flex({
      components: [
        {
          Component: Component.Search(),
          grow: true,
        },
        { Component: Component.Darkmode() },
      ],
    }),
    Component.Explorer({
      title: "Проводник",
      filterFn: (node) => node.slugSegment !== "tags" && node.slugSegment !== "Темы",
      mapFn: explorerThemeFolderTitle,
    }),
  ],
  right: [],
}
