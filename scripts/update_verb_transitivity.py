#!/usr/bin/env python3
"""Дополнить только «Заметки» проверенной переходностью; по умолчанию dry-run.

Источник решений: docs/verb-transitivity/data.json. --apply пишет JSON;
--anki обновляет только поле «Заметки» в существующих заметках Anki.
Перед записью проверяется неизменность снимка Anki.
"""
from __future__ import annotations
import argparse
import json
import re
from collections import Counter
from pathlib import Path

from sync_json_to_anki_connect import invoke

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'docs/verb-transitivity/data.json'
MARKER = 'Переходность: '


def augmented(original: str, addition: str) -> str:
    original = '' if original.startswith(MARKER) else re.split(r'(?:<br>\s*){2}' + MARKER, original, maxsplit=1)[0]
    return original.rstrip() + ('<br><br>' if original.strip() else '') + MARKER + addition


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--anki', action='store_true')
    ap.add_argument('--url', default='http://127.0.0.1:8765')
    ap.add_argument('--snapshot', type=Path)
    ap.add_argument('--red-cards', type=Path)
    ap.add_argument('--backup', type=Path, default=Path('/tmp/verb-transitivity-backup.json'))
    args = ap.parse_args()
    if args.anki and (not args.apply or not args.snapshot):
        ap.error('--anki требует --apply и --snapshot')
    records = json.loads(DATA.read_text())
    assert len({x['path'] for x in records}) == len(records)
    snapshots = json.loads(args.snapshot.read_text()) if args.snapshot else []
    by_word: dict[str, list] = {}
    for note in snapshots:
        by_word.setdefault(note['fields']['Слово']['value'], []).append(note)
    red = json.loads(args.red_cards.read_text()) if args.red_cards else []
    red_by_nid = {c['note']: c for c in red}
    planned, backup = [], []
    for record in records:
        path = ROOT / record['path']
        before = json.loads(path.read_text())
        assert before['Слово'] == record['word']
        data = dict(before)
        notes = by_word.get(record['word'], [])
        if args.anki:
            assert len(notes) <= 1, (record['word'], len(notes))
        note = notes[0] if len(notes) == 1 else None
        # Красный флаг: переносим исправленную версию Anki в JSON до дополнения.
        if note and note['noteId'] in red_by_nid:
            data.update({k: f['value'] for k, f in note['fields'].items()})
            data['Теги'] = note['tags']
        data['Заметки'] = augmented(str(data.get('Заметки', '')), record['note'])
        backup.append({'path': record['path'], 'json': before, 'anki': note})
        planned.append((record, path, data, note))
    if not args.apply:
        print(json.dumps({'cards': len(planned), 'types': Counter(r['type'] for r in records)}, ensure_ascii=False))
        return
    # Сохраняем полный снимок до первой мутации. При повторном запуске не затираем.
    if not args.backup.exists():
        args.backup.write_text(json.dumps(backup, ensure_ascii=False, indent=2) + '\n')
    if args.anki:
        fields = invoke(args.url, 'modelFieldNames', modelName='Японские слова')
        assert 'Заметки' in fields
        for offset in range(0, len(planned), 100):
            batch = [p for p in planned[offset:offset + 100] if p[3] is not None]
            current = invoke(args.url, 'notesInfo', notes=[n['noteId'] for *_, n in batch])
            cur = {n['noteId']: n for n in current}
            for record, _, data, note in batch:
                old = note['fields']['Заметки']['value']
                now = cur[note['noteId']]['fields']['Заметки']['value']
                assert now in (old, data['Заметки']), ('Anki изменена после снимка', record['word'])
    synced = []
    for record, path, data, note in planned:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
        if args.anki and note:
            invoke(args.url, 'updateNoteFields', note={'id': note['noteId'], 'fields': {'Заметки': data['Заметки']}})
            synced.append(note['noteId'])
    if args.anki:
        for offset in range(0, len(planned), 100):
            batch = [p for p in planned[offset:offset + 100] if p[3] is not None]
            current = {n['noteId']: n for n in invoke(args.url, 'notesInfo', notes=[n['noteId'] for *_, n in batch])}
            for record, path, data, note in batch:
                after = current[note['noteId']]
                assert after['fields']['Заметки']['value'] == data['Заметки'], record['word']
                for key, field in note['fields'].items():
                    if key != 'Заметки':
                        assert after['fields'][key]['value'] == field['value'], (record['word'], key)
                assert after['tags'] == note['tags']
                if note['noteId'] in red_by_nid:
                    # Поля JSON должны совпасть с исправленной версией Anki.
                    local = json.loads(path.read_text())
                    assert all(local[k] == f['value'] for k, f in after['fields'].items())
                    invoke(args.url, 'setSpecificValueOfCard', card=red_by_nid[note['noteId']]['cardId'], keys=['flags'], newValues=[0])
    report = {'total': len(records), 'types': dict(Counter(r['type'] for r in records)),
              'anki_updated': len(synced), 'anki_missing': [r['word'] for r, _, _, n in planned if n is None],
              'red_flags_synced': [r['word'] for r, _, _, n in planned if n and n['noteId'] in red_by_nid]}
    (ROOT / 'docs/verb-transitivity/result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
