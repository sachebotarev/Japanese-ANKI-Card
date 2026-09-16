#!/usr/bin/env python3
"""Сборка только проверенных строк импорта Minna; существующие карточки не изменяет."""
import json,re,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'docs/minna-import-2026-09-16'
TODO={x['index']:x for x in json.loads((DATA/'minna_todo.json').read_text())}
# Значения разделены следующим ключом, чтобы разрешить пробелы в пояснениях.
def kanji_map():
 s=(DATA/'kanji.txt').read_text(); return {m[1]:m[2].strip() for m in re.finditer(r'([一-龯])=(.*?)(?=\s[一-龯]=|$)',s,re.S)}
BASIC=set((DATA/'basic-kanji-book-1.txt').read_text().strip())
def templates(kind,w,n,a):
 n=n.split(';')[0]
 if kind in ('small','device','furniture'):
  return ([f'これは{{{w}}}です。',f'この店で{{{w}}}を売っています。',f'明日使うので、{{{w}}}を買って、家に持って帰りました。'],[f'Это {n}.',f'В этом магазине продают {a}.',f'Завтра мне понадобится {n}, поэтому я купил и принёс домой {a}.'])
 if kind=='document':return ([f'これは{{{w}}}です。',f'{{{w}}}は机の上にあります。',f'明日必要なので、{{{w}}}をかばんに入れて、忘れないようにしました。'],[f'Это {n}.',f'{n.capitalize()} находится на столе.',f'Завтра мне понадобится {n}, поэтому я положил это в сумку, чтобы не забыть.'])
 if kind=='food':return ([f'{{{w}}}を食べます。',f'昨日、友達と{{{w}}}を食べました。',f'お腹がすいていたので、店で{{{w}}}を買って、公園で食べました。'],[f'Я ем {a}.',f'Вчера я ел {a} с другом.',f'Я был голоден, поэтому купил {a} в магазине и съел в парке.'])
 if kind=='ingredient':return ([f'これは{{{w}}}です。',f'母は料理に{{{w}}}を使います。',f'晩ご飯を作ろうと思ったら、{{{w}}}がなかったので、買いに行きました。'],[f'Это {n}.',f'Мама использует {a} для приготовления еды.',f'Когда я собрался готовить ужин, оказалось, что дома нет нужного ингредиента — {n}, поэтому я пошёл за покупками.'])
 if kind=='clothes':return ([f'これは{{{w}}}です。',f'昨日、新しい{{{w}}}を買いました。',f'明日出かけるので、新しい{{{w}}}を出して、かばんの隣に置いておきました。'],[f'Это {n}.',f'Вчера я купил обновку — {a}.',f'Завтра я ухожу из дома, поэтому достал обновку — {a} — и заранее положил рядом с сумкой.'])
 if kind=='animal':return ([f'{{{w}}}がいます。',f'この本には{{{w}}}の写真があります。',f'{{{w}}}がよく見えるように、少し近くへ行って、写真を撮りました。'],[f'Здесь есть {n}.',f'В этой книге есть фотография: на ней {n}.',f'Чтобы лучше видеть {a}, я подошёл немного ближе и сделал фотографию.'])
 if kind=='plant':return ([f'これは{{{w}}}です。',f'庭に{{{w}}}があります。',f'{{{w}}}の花が咲いたので、庭へ出て、写真を撮りました。'],[f'Это {n}.',f'В саду растёт {n}.',f'Зацвела {n}, поэтому я вышел в сад и сделал фотографию.'])
 if kind in ('place','room'):
  return ([f'あそこに{{{w}}}があります。',f'昨日、友達と{{{w}}}に行きました。',f'{{{w}}}に行く前に、場所を調べて、友達と駅で待ち合わせました。'],[f'Вон там есть {n}.',f'Вчера мы с другом посетили {a}.',f'Перед тем как посетить {a}, я выяснил, где это находится, и встретился с другом на станции.'])
 if kind=='fixture':return ([f'あそこに{{{w}}}があります。',f'{{{w}}}の前に人がいます。',f'{{{w}}}を探していたら、親切な人が来て、場所を教えてくれました。'],[f'Вон там есть {n}.',f'Там стоит человек, а прямо за ним — {n}.',f'Когда я искал {a}, подошёл доброжелательный человек и подсказал, где искать.'])
 if kind=='event':return ([f'{{{w}}}は明日です。',f'母も{{{w}}}に行きます。',f'{{{w}}}に行く前に、場所を調べて、友達と駅で待ち合わせました。'],[f'Завтра — {n}.',f'Мама тоже собирается посетить {a}.',f'Перед тем как посетить {a}, я выяснил, где это будет, и встретился с другом на станции.'])
 if kind=='exam':return ([f'{{{w}}}は明日です。',f'明日の{{{w}}}は難しいです。',f'{{{w}}}に遅れないように、早く起きて、朝ご飯を食べずに家を出ました。'],[f'{n.capitalize()} будет завтра.',f'Завтра предстоит сложное испытание — {n}.',f'Чтобы не опоздать на {a}, я рано встал и вышел из дома, не позавтракав.'])
 if kind=='profession':return ([f'兄は{{{w}}}です。',f'昨日、{{{w}}}と話しました。',f'仕事のことを聞きたかったので、{{{w}}}に会って、いろいろ教えてもらいました。'],[f'Мой старший брат — {n}.',f'Вчера мой собеседник был по профессии {n}.',f'Я хотел узнать о работе, поэтому встретил специалиста — {a} — и получил от него много полезных объяснений.'])
 if kind=='vehicle':return ([f'これは{{{w}}}です。',f'写真の{{{w}}}は大きいです。',f'{{{w}}}を近くで見たかったので、外に出て、写真を撮りました。'],[f'Это {n}.',f'На фотографии — {n} большого размера.',f'Я хотел увидеть {a} вблизи, поэтому вышел наружу и сделал фотографию.'])
 if kind in ('watch','watchobject'):return ([f'これは{{{w}}}です。',f'昨日、{{{w}}}を見ました。',f'{{{w}}}を見るのは初めてだったので、友達にいろいろ説明してもらいました。'],[f'Это {n}.',f'Вчера я видел {a}.',f'Я впервые видел {a}, поэтому попросил друга объяснить мне разные детали.'])
 if kind=='book':return ([f'{{{w}}}を読みます。',f'昨日、図書館で{{{w}}}を読みました。',f'{{{w}}}が面白かったので、家に帰ってから、家族にその話をしました。'],[f'Я читаю {a}.',f'Вчера я читал {a} в библиотеке.',f'Мне понравилось читать {a}, поэтому, вернувшись домой, я рассказал об этом семье.'])
 raise ValueError(kind)
def build(idx,topic,reading,translation,hint,jp,ru,notes='',tags=None,word=None,breakdown=None):
 if str(idx) in json.loads((DATA/'manual-exclusions.json').read_text()):return
 item=TODO[idx];word=word or item['word'];km=kanji_map()
 chars=list(dict.fromkeys(re.findall('[一-龯]',word)))
 missing=[c for c in chars if c not in km]
 if missing and not breakdown:raise ValueError((word,'нет разбора',missing))
 examples=[];blank=[]
 for ex in jp:
  assert len(re.findall(r'\{[^{}]+\}',ex))>=1,(word,ex)
  examples.append(re.sub(r'\{([^{}]+)\}',r"<span class='study-word'>\1</span>",ex))
  blank.append(re.sub(r'\{[^{}]+\}','_____',ex))
 assert len(jp)==len(ru)==3
 lesson=int(item['source']['Lesson Number']); lesson_tag=f'みんな初級{"I" if lesson<=25 else "II"}-第{lesson if lesson<=25 else lesson-25:02}課'
 payload={'Слово':word,'Чтение':reading,'Перевод':translation,'Подсказка':hint,'Пример':'<br>'.join(examples),'Пример без слова':'<br>'.join(blank),'Пример перевод':'<br>'.join(ru),'Картинка':f'masterpiece, best quality, anime illustration, square 1:1, 512x512, scene: {ru[2]}, visual focus: {translation}, clear physical objects, natural poses, no text, no letters, no watermark. Negative: text, letters, typography, logo, bad anatomy.','Произношение':'','Заметки':notes,'Кандзи-разбор':breakdown or ('; '.join(c+' — '+km[c] for c in chars) if chars else 'Кандзи нет.'),'Показать фуригану':'Y' if set(chars)-BASIC else 'N','Теги':[topic,*(tags or ['名詞']),json.loads((DATA/'jlpt-levels.json').read_text()).get(str(idx),'N5' if lesson<=25 else 'N4'),'みんなの日本語',lesson_tag]}
 out=ROOT/'Карточки'/topic/(word+'.json')
 manifest_path=DATA/'created.json'; manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else []
 record={'index':idx,'word':word,'path':str(out.relative_to(ROOT)),'source_id':item['source']['id']}
 if out.exists():
  assert any(x['path']==record['path'] for x in manifest),f'Уже существовала: {out}'
  if os.environ.get('MINNA_REFRESH')!='1':return
  old=json.loads(out.read_text());payload['Произношение']=old.get('Произношение','')
  out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n');return
 words=ROOT/'Слова'/topic
 lines=set(words.read_text().splitlines()) if words.exists() else set();lines.add(word)
 words.write_text('\n'.join(sorted({x.strip() for x in lines if x.strip()}))+'\n')
 out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
 manifest.append(record);manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':
 for line in (DATA/'nouns.txt').read_text().splitlines():
  idx,topic,kind,reading,n,a,hint=line.split('|');idx=int(idx);w=TODO[idx]['word'];jp,ru=templates(kind,w,n,a)
  build(idx,topic,reading,n,hint,jp,ru,notes=f'Слово из урока {TODO[idx]["source"]["Lesson Number"]} Minna no Nihongo. '+hint)
 print('Создано:',len(json.loads((DATA/'created.json').read_text())))
