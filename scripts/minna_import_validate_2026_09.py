"""Проверка только новых карточек; с --upload-media загружает проверенные MP3."""
import json,re,hashlib,subprocess,urllib.request,base64,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/minna-import-2026-09-16'
rows=json.loads((D/'created.json').read_text());logs={r['file']:r for line in (D/'audio-log.jsonl').read_text().splitlines() if (r:=json.loads(line))}
media=[];notes=[];words=set();topics=set()
for row in rows:
 p=ROOT/row['path'];d=json.loads(p.read_text());w=d['Слово'];assert w not in words;words.add(w);topics.add(p.parent.name)
 assert len(d)==13,(w,d.keys())
 assert all(isinstance(v,str) for k,v in d.items() if k!='Теги')
 assert all(len(d[f].split('<br>'))==3 for f in ['Пример','Пример без слова','Пример перевод'])
 assert all("<span class='study-word'>" in ex for ex in d['Пример'].split('<br>'))
 assert re.sub(r"<span class='study-word'>.*?</span>",'_____',d['Пример'])==d['Пример без слова']
 assert w in (ROOT/'Слова'/p.parent.name).read_text().splitlines()
 assert p.parent.name in d['Теги'] and len([t for t in d['Теги'] if t.startswith('みんな初級')])==1
 files=re.findall(r'\[sound:([^\]]+)\]',d['Произношение']);assert len(files)==4,w
 texts=[w,*[re.sub('<[^>]+>','',x) for x in d['Пример'].split('<br>')]]
 for i,(name,text) in enumerate(zip(files,texts)):
  name=w+('_слово' if i==0 else '_пример_'+str(i))+'.mp3'
  f=ROOT/'Произношение'/p.parent.name/name;log=logs[str(f.relative_to(ROOT))]
  assert f.stat().st_size>1000 and log['sha256']==hashlib.sha256(f.read_bytes()).hexdigest(),f
  assert log['text']==text,(w,log['text'],text)
  assert log['speed']==0.9
  assert log['speaker'] in ('かりん(現実20代女子AIボイチェン@リアボVC公式モデル)','阿井田 茂','にせ','わかな(現実20代女子AIボイチェン@リアボVC公式モデル)')
  media.append(f)
 notes.append({'fields':{k:('' if k=='Картинка' else v) for k,v in d.items() if k!='Теги'},'tags':d['Теги']})
for t in topics:
 lines=(ROOT/'Слова'/t).read_text().splitlines();assert lines==sorted(set(lines)) and all(lines),t
assert len({f.name for f in media})==len(media)
def check(f):
 r=subprocess.run(['ffmpeg','-v','error','-i',str(f),'-f','null','-'],capture_output=True);assert r.returncode==0,(f,r.stderr.decode());return True
with ThreadPoolExecutor(max_workers=6) as ex:assert all(ex.map(check,media))
(D/'anki-payload.json').write_text(json.dumps(notes,ensure_ascii=False))
print('Validated',len(rows),'notes and',len(media),'MP3',flush=True)
def api(action,**params):
 result=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765',data=json.dumps({'action':action,'version':6,'params':params}).encode()),timeout=120));assert result['error'] is None,result;return result['result']
if '--upload-media' in sys.argv:
 mapping={}
 for i,f in enumerate(media):
  result=api('storeMediaFile',filename=f.name,data=base64.b64encode(f.read_bytes()).decode(),deleteExisting=False);assert result
  mapping[f.name]=result
  if i%200==0:print('uploaded',i,flush=True)
 (D/'media-names.json').write_text(json.dumps(mapping,ensure_ascii=False,indent=2)+'\n')
 for row in rows:
  p=ROOT/row['path'];d=json.loads(p.read_text());w=d['Слово'];d['Произношение']=''.join('[sound:'+mapping[w+suffix+'.mp3']+']' for suffix in ['_слово','_пример_1','_пример_2','_пример_3']);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
 notes=[]
 for r in rows:
  d=json.loads((ROOT/r['path']).read_text());notes.append({'fields':{k:('' if k=='Картинка' else v) for k,v in d.items() if k!='Теги'},'tags':d['Теги']})
 (D/'anki-payload.json').write_text(json.dumps(notes,ensure_ascii=False))
 print('UPLOADED',len(media),flush=True)
(D/'validation.json').write_text(json.dumps({'notes':len(rows),'mp3':len(media),'topics':len(topics),'checks':['three aligned examples','study-word masks','unique words and media names','normalized word lists','audio text and SHA256','voice whitelist and 90% speed','full MP3 decoding']},ensure_ascii=False,indent=2)+'\n')
