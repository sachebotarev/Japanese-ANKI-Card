"""Последние смысловые исправления; затрагивает только манифест импорта."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'docs/minna-import-2026-09-16'
pronouns=set('これ それ あれ ここ そこ あそこ こちら あちら こっち そっち あっち 君'.split())
adnominals=set('この その あの こんな そんな あんな'.split())
conjunctions=set('でも それなら それに それで すると しかし それでも では'.split())
interjections=set('いいえ えっ どうぞ あ ああ さあ へえ うん ううん えーと うーん わあ ええ はい'.split())
expressions={3,16,63,64,66,76,80,82,103,106,108,146,148,150,151,162,163,175,176,185,200,204,211,226,248,268,369,386,395,465,507,566,598,641,671,752,769,772,773,774,804,820}
for r in json.loads((DATA/'created.json').read_text()):
 p=ROOT/r['path'];d=json.loads(p.read_text());w=d['Слово'];idx=r['index']
 pos=next((tag for group,tag in [(pronouns,'代名詞'),(adnominals,'連体詞'),(conjunctions,'接続詞'),(interjections,'感動詞')] if w in group),None)
 if idx in expressions:pos='慣用表現'
 if pos:d['Теги']=[pos if t=='名詞' else t for t in d['Теги']]
 if w=='いただく':d['Теги']=[t for t in d['Теги'] if not t.startswith('みんな初級')]+['みんな初級II-第16課']
 if w in {'表','方','金'}:d['Кандзи-разбор']={'表':'表 — лицевая сторона; поверхность','方':'方 — человек (уважительно); направление; способ','金':'金 — золото; металл; деньги'}[w]
 if w=='ガム':
  jp=['私は{ガム}をかみます。','弟は食事の後で{ガム}をかみます。','眠くなったので、店で{ガム}を買って、少しかんでから勉強を続けました。']
  ru=['Я жую жвачку.','Младший брат жуёт жвачку после еды.','Мне захотелось спать, поэтому я купил жвачку в магазине, немного пожевал и продолжил заниматься.']
  d['Пример']='<br>'.join(re.sub(r'\{(.+?)\}',r"<span class='study-word'>\1</span>",s) for s in jp)
  d['Пример без слова']='<br>'.join(re.sub(r'\{.+?\}','_____',s) for s in jp);d['Пример перевод']='<br>'.join(ru)
  d['Картинка']='anime illustration, square 1:1, one student at a desk, chewing gum from an open gum packet beside a notebook, evening study room, visual focus on gum and chewing, no text, no letters, no watermark'
 if 'Импорт::Minna_2026_09_16' not in d['Теги']:d['Теги'].append('Импорт::Minna_2026_09_16')
 p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
