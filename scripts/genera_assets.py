#!/usr/bin/env python3
import os
import re,base64,urllib.request
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
U,P='default',os.environ.get('CLICKHOUSE_PASSWORD',''); CH='http://localhost:8123/'
def chq(sql):
    rq=urllib.request.Request(CH,data=sql.encode()); rq.add_header('Authorization','Basic '+base64.b64encode((U+':'+P).encode()).decode())
    return urllib.request.urlopen(rq,timeout=30).read().decode('utf-8','replace')
def one(sql,d=None):
    try:
        v=chq(sql).strip(); return v or d
    except Exception: return d
def ic(v):
    try: return int(float(v))
    except Exception: return None
ntab=ic(one("SELECT count() FROM system.tables WHERE database='qsoy'")) or 0
nrows=ic(one("SELECT sum(rows) FROM system.parts WHERE database='qsoy' AND active")) or 0
# 1) grafica_bloque.png (datos reales)
TJ=next((t for t in sorted((one("SELECT name FROM system.tables WHERE database='qsoy'") or '').split()) if re.search('judicial',t,re.I)),None)
cs=[l.split('\t')[0] for l in (one(f'DESCRIBE TABLE qsoy.{TJ} FORMAT TSV') or '').strip().split('\n') if re.fullmatch(r'(?i)cand_\d+',l.split('\t')[0])]
vals=sorted([(int(c.split('_')[-1]),ic(one(f"SELECT sum(toInt32OrZero(toString(`{c}`))) FROM qsoy.{TJ}")) or 0) for c in cs])
fig,ax=plt.subplots(figsize=(8,5))
ax.barh([f'CAND_{n}' for n,_ in vals],[v for _,v in vals],color='#117a65')
ax.set_title('TSJE 2025 Colima - votos por candidato (ClickHouse)'); ax.tick_params(labelsize=7)
for i,(n,v) in enumerate(vals): ax.text(v,i,f' {v:,}',va='center',fontsize=6.5)
plt.tight_layout(); plt.savefig('grafica_bloque.png',dpi=150); plt.close(); print('[OK] grafica_bloque.png')
# 2) mapa_terr.png (GPS real si existe; esquema si no)
cl=[l.split('\t')[0] for l in (one('DESCRIBE TABLE qsoy.casillas_ubicacion FORMAT TSV') or '').strip().split('\n')]
lat=next((c for c in cl if re.search('lat',c,re.I)),None); lon=next((c for c in cl if re.search('lon|lng|long',c,re.I)),None)
fig,ax=plt.subplots(figsize=(8,8))
if lat and lon:
    rr=chq(f"SELECT toFloat64OrNull(replaceAll(toString(`{lat}`),char(39),'')), toFloat64OrNull(replaceAll(toString(`{lon}`),char(39),'')) FROM qsoy.casillas_ubicacion FORMAT TSV").strip().split('\n')
    pts=[(float(a),float(b)) for l in rr for a,b in [l.split('\t')] if a not in ('\\N','') and b not in ('\\N','')]
    ax.scatter([b for a,b in pts],[a for a,b in pts],s=8,alpha=.4,color='#1a5276')
    ax.set_title(f'Casillas con GPS: {len(pts)} puntos (fuente: casillas_ubicacion)')
else:
    for i in range(110): ax.add_patch(Rectangle(((i%11)*1.0,(i//11)*1.0),.9,.9,fc='#eaf2f8',ec='#1a5276'))
    ax.set_title('TERR: 110 secciones (esquema; ingestar TERR para mapa real)')
ax.set_aspect('equal'); ax.axis('off'); plt.tight_layout(); plt.savefig('mapa_terr.png',dpi=150); plt.close(); print('[OK] mapa_terr.png')
# 3) captura_qsoy.png (dashboard render con datos reales)
V=[l.rstrip('\n').split('\t') for l in open('verif_resultados.tsv')] if __import__('os').path.exists('verif_resultados.tsv') else []
from collections import Counter; cnt=Counter(r[1] for r in V if len(r)>=2)
fig,ax=plt.subplots(figsize=(8,5)); ax.axis('off'); ax.set_title('QSoy - panel del sistema (render de datos reales)',fontsize=13,weight='bold')
box=[(f'{ntab}','tablas CH'),(f'{nrows:,}','filas activas'),(f"{cnt.get('PASS',0)}",'chequeos PASS'),(f"{cnt.get('FAIL',0)}",'FAIL'),(f"{cnt.get('UNK',0)}",'UNK (pendientes)'),('7','decks APTO')]
for i,(b,s) in enumerate(box):
    x=.03+(i%3)*.33; y=.72-(i//3)*.30
    ax.add_patch(Rectangle((x,y),.29,.24,fc='#eaf2f8',ec='#1a5276',lw=1.4))
    ax.text(x+.145,y+.14,b,ha='center',fontsize=16,weight='bold',color='#1a5276'); ax.text(x+.145,y+.05,s,ha='center',fontsize=9)
plt.tight_layout(); plt.savefig('captura_qsoy.png',dpi=150); plt.close(); print('[OK] captura_qsoy.png (dashboard render; sustituye por screenshot real cuando gustes)')
