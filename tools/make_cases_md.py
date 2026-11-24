#!/usr/bin/env python3
import os, sys, sqlite3
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..', 'verify'))
from fixtures.book_cases import CASES
con = sqlite3.connect(':memory:'); con.executescript(open(os.path.join(HERE, '..', 'gua.sql'), encoding='utf-8').read())
out = []
for c in CASES:
    mv = '、'.join(map(str, c['mv'])) or '静'
    chg = c['label'] if c['mv'] else '（静卦）'
    md = f"{c['m'] or '（原文未记月）'}月{c['d']}日"
    note = f"<br>※{c['note']}" if c.get('note') else ''
    out.append(f"| {c['id']} | {c['ch']} | {c['q']} | {c['base']} → {chg}（动{mv}） | {md} | {c['j']} | {c['o']} | {c['l']}{note} | {len(c['a'])+1} |")
print('\n'.join(out))
