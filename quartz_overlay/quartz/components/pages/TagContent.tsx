import { QuartzComponent, QuartzComponentConstructor, QuartzComponentProps } from "../types"
import style from "../styles/listPage.scss"
import { byDateAndAlphabeticalFolderFirst, SortFn } from "../PageList"
import { FullSlug, getAllSegmentPrefixes, resolveRelative, simplifySlug } from "../../util/path"
import { Root } from "hast"
import { htmlToJsx } from "../../util/jsx"
import { i18n } from "../../i18n"
import { ComponentChildren } from "preact"

interface TagContentOptions {
  sort?: SortFn
}

export default ((opts?: Partial<TagContentOptions>) => {
  const options: TagContentOptions = { ...opts }

  const TagContent: QuartzComponent = (props: QuartzComponentProps) => {
    const { tree, fileData, allFiles, cfg } = props
    const slug = fileData.slug

    if (!(slug?.startsWith("tags/") || slug === "tags")) {
      throw new Error(`Component "TagContent" tried to render a non-tag page: ${slug}`)
    }

    const tag = simplifySlug(slug.slice("tags/".length) as FullSlug)
    const allPagesWithTag = (tag: string) =>
      allFiles.filter((file) =>
        (file.frontmatter?.tags ?? []).flatMap(getAllSegmentPrefixes).includes(tag),
      )

    const content = (
      (tree as Root).children.length === 0
        ? fileData.description
        : htmlToJsx(fileData.filePath!, tree)
    ) as ComponentChildren
    const cssClasses: string[] = fileData.frontmatter?.cssclasses ?? []
    const classes = cssClasses.join(" ")
    if (tag === "/") {
      // The default Quartz index renders a PageList under every tag. With thousands
      // of cards this repeats the same links many times and makes /tags/ slow.
      const tagCounts = new Map<string, number>()
      for (const file of allFiles) {
        const fileTags = new Set((file.frontmatter?.tags ?? []).flatMap(getAllSegmentPrefixes))
        for (const fileTag of fileTags) {
          tagCounts.set(fileTag, (tagCounts.get(fileTag) ?? 0) + 1)
        }
      }
      const tags = [...tagCounts.keys()].sort((a, b) => a.localeCompare(b))
      return (
        <div class="popover-hint">
          <article class={classes}>
            <p>{content}</p>
          </article>
          <p>{i18n(cfg.locale).pages.tagContent.totalTags({ count: tags.length })}</p>
          <ul>
            {tags.map((tag) => {
              const tagListingPage = `/tags/${tag}` as FullSlug
              const href = resolveRelative(fileData.slug!, tagListingPage)

              return (
                <li>
                  <a class="internal tag-link" href={href}>
                    {tag}
                  </a>{" "}
                  ({tagCounts.get(tag)})
                </li>
              )
            })}
          </ul>
        </div>
      )
    } else {
      const pages = allPagesWithTag(tag).sort(options.sort ?? byDateAndAlphabeticalFolderFirst(cfg))

      return (
        <div class="popover-hint">
          <article class={classes}>{content}</article>
          <div class="page-listing">
            <p>{i18n(cfg.locale).pages.tagContent.itemsUnderTag({ count: pages.length })}</p>
            <ul>
              {pages.map((page) => (
                <li>
                  <a class="internal" href={resolveRelative(fileData.slug!, page.slug!)}>
                    {page.frontmatter?.title}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )
    }
  }

  TagContent.css = style
  return TagContent
}) satisfies QuartzComponentConstructor
