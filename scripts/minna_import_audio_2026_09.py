"""Возобновляемая озвучка проверенного манифеста, с журналом текста и голосов."""
import json,re,random,hashlib,html
from pathlib import Path
import generate_aivis_audio as a
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/'docs/minna-import-2026-09-16'
a.ALLOWED_TTS_SPEAKERS=('かりん(現実20代女子AIボイチェン@リアボVC公式モデル)','阿井田 茂','にせ','わかな(現実20代女子AIボイチェン@リアボVC公式モデル)')
speakers=a.speakers_by_name(a.DEFAULT_ENGINE_URL);pool=a.compatible_whitelist(speakers,style_name='ノーマル');assert pool
log=DATA/'audio-log.jsonl';prior={r['file']:r for line in log.read_text().splitlines() if (r:=json.loads(line))}
made=0
for record in json.loads((DATA/'created.json').read_text()):
 p=ROOT/record['path'];d=json.loads(p.read_text());word=d['Слово'];out=ROOT/'Произношение'/p.parent.name;out.mkdir(exist_ok=True)
 texts=[word,*a.parse_examples(d['Пример'])];spoken=[d['Чтение'],*texts[1:]]
 if record['index'] in {35,504,540,621,544,516,1016,1004}:
  spoken[1:]=[html.unescape(re.sub('<[^>]+>','',re.sub(r"<span class='study-word'>.*?</span>",d['Чтение'],ex))) for ex in d['Пример'].split('<br>')]
 for i,(text,synthesis) in enumerate(zip(texts,spoken)):
  dest=out/(word+('_слово' if i==0 else '_пример_'+str(i))+'.mp3');relative=str(dest.relative_to(ROOT));old=prior.get(relative,{})
  if dest.exists() and old.get('synthesis_text',old.get('text'))==synthesis and old.get('sha256')==hashlib.sha256(dest.read_bytes()).hexdigest():continue
  speaker=random.choice(pool);style=a.pick_style_id_from_speaker(speakers[speaker],'ノーマル');a.generate_audio(a.DEFAULT_ENGINE_URL,style,synthesis,dest)
  with log.open('a') as f:f.write(json.dumps({'file':relative,'text':text,'synthesis_text':synthesis,'speaker':speaker,'speed':0.9,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()},ensure_ascii=False)+'\n')
  made+=1
 d['Произношение']=a.sound_tags(word);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 print(record['index'],word,'generated',made,flush=True)
print('DONE',made,flush=True)
