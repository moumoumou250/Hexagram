import sqlite3,os
if os.path.exists('rec.db'): os.remove('rec.db')
c=sqlite3.connect('rec.db',uri=True)
s=open('liuyao_schema_v2.sql').read()
c.executescript(s.split('-- 第二部分')[0])
c.execute("ATTACH DATABASE 'file:najia_v5.db?mode=ro' AS fix")
c.executescript(s.split('-- 第二部分')[1].split('\n',1)[1])
# 天雷无妄 id?
hid=c.execute("select hexagram_id from fix.hexagrams where name='天雷无妄'").fetchone()[0]
c.execute("insert into gua_record(gua_id,question,month_branch,day_ganzhi,hexagram_id,move_mask,yong_liuqin) values('t1','测试','寅','戊午',?,3,'妻财')",(hid,))
for v in ['v_gua','v_yao','v_dong_effect','v_shi_ying','v_yong_candidates']:
    cur=c.execute(f'select * from {v}'); print(v,[d[0] for d in cur.description][:8]); 
    for r in cur.fetchall()[:6]: print(' ',r)
try: c.execute("insert into fix.dizhi values('x',13,'水','阳',13)")
except Exception as e: print('ro ok:',e)
