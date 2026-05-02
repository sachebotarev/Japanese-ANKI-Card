import GraphConstructor from "../Graph"
import { QuartzComponentConstructor } from "../types"
// @ts-ignore — esbuild-плагин Quartz инлайнит файл как строку.
import script from "./scripts/myGraph.inline"

/**
 * Обёртка над стандартным `Component.Graph`: использует те же опции,
 * но подменяет inline-скрипт на копию `graph.inline.ts` с двумя правками:
 *  1) `pixi.preference: "webgl"` — у части браузеров WebGPU «вешает» первый кадр;
 *  2) старт `renderLocalGraph` через `requestIdleCallback`, чтобы навигация
 *     SPA не казалась «зависшей», пока инициализируется Pixi.
 *
 * Это единственный способ кастомизировать инлайн-скрипт компонента
 * без правки исходников Quartz.
 */
const MyGraph: QuartzComponentConstructor = (opts) => {
  const Component = GraphConstructor(opts)
  Component.afterDOMLoaded = script
  return Component
}

export default MyGraph
