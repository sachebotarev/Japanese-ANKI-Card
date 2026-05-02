import path from "path"
import { FilePath } from "./path"
import { globby } from "globby"

export function toPosixPath(fp: string): string {
  return fp.split(path.sep).join("/")
}

export async function glob(
  pattern: string,
  cwd: string,
  ignorePatterns: string[],
): Promise<FilePath[]> {
  const fps = (
    await globby(pattern, {
      cwd,
      ignore: ignorePatterns,
      // В этом репозитории `quartz/content/` в корневом .gitignore: при true
      // Quartz не видит ни одного .md и не собирает index.html (на Pages остаётся только RSS).
      gitignore: false,
    })
  ).map(toPosixPath)
  return fps as FilePath[]
}
