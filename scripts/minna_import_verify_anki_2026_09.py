"""Сверяет созданные заметки и импортированные MP3 с локальным манифестом."""
import json,urllib.request,base64,hashlib,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'docs/minna-import-2026-09-16'
def api(action,**params):
 r=json.load(urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8765',data=json.dumps({'action':action,'version':6,'params':params}).encode()),timeout=120));assert not r['error'],r;return r['result']
rows=json.loads((D/'created.json').read_text());results=json.loads((D/'anki-results.json').read_text());ids=[x['note_id'] for batch in results for x in batch['results'] if x['status']=='created'];assert len(ids)==len(rows)==len(set(ids))
notes=api('notesInfo',notes=ids);byword={x['fields']['Слово']['value']:x for x in notes};count=0
for row in rows:
 p=ROOT/row['path'];d=json.loads(p.read_text());n=byword[d['Слово']]
 for k,v in d.items():
  if k=='Теги':continue
  assert n['fields'][k]['value']==('' if k=='Картинка' else v),(d['Слово'],k)
 assert {t.casefold() for t in n['tags']}=={t.casefold() for tag in d['Теги'] for t in tag.split()},(d['Слово'],n['tags'],d['Теги'])
 for i,name in enumerate(re.findall(r'\[sound:([^\]]+)\]',d['Произношение'])):
  audio=api('retrieveMediaFile',filename=name);assert audio is not False,name
  actual=base64.b64decode(audio);local=(ROOT/'Произношение'/p.parent.name/(d['Слово']+('_слово' if i==0 else '_пример_'+str(i))+'.mp3')).read_bytes();assert hashlib.sha256(actual).digest()==hashlib.sha256(local).digest(),name;count+=1
before=Path('/tmp/pre-import-target.json')
if before.exists():
 original=json.loads(before.read_text());now={n['noteId']:n for n in api('notesInfo',notes=[n['noteId'] for n in original])}
 for n in original:
  for key,value in n['fields'].items():
   assert now[n['noteId']]['fields'][key]['value'].replace("class='study-word'",'class="study-word"')==value['value'].replace("class='study-word'",'class="study-word"'),(n['noteId'],key)
  assert set(now[n['noteId']]['tags'])==set(n['tags']),n['noteId']
print('Verified',len(ids),'notes,',count,'media; existing fields/tags unchanged',flush=True)
(D/'anki-verification.json').write_text(json.dumps({'new_notes':len(ids),'new_cards':sum(len(n['cards']) for n in notes),'media_verified_by_sha256':count,'target_notes_after':len(api('findNotes',query='deck:"Японские слова"')),'existing_fields_tags_unchanged':before.exists(),'note_ids':ids},ensure_ascii=False,indent=2)+'\n')
