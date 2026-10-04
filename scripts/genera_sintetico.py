#!/usr/bin/env python3
# genera_sintetico.py — padron 100% sintetico, cero relacion con personas reales
# Ej: python3 scripts/genera_sintetico.py --n 100000000 --cargar --tabla padron_sintetico
import argparse, random, os, urllib.request, urllib.parse, time
N=["Maria","Jose","Juan","Guadalupe","Ana","Luis","Carlos","Rosa","Miguel","Carmen","Josefa","Pedro"]
P=["Garcia","Martinez","Lopez","Hernandez","Perez","Sanchez","Ramirez","Toro","Villa","Rocha","Vega","Campos"]
M=["Diaz","Cruz","Alvarez","Romero","Navarro","Morano","Castro","Ortiz","Rubio","Soto","Mata","Rios"]
C=["Revolucion","Hidalgo","Juarez","Zaragoza","Allende","Morelos","Matamoros","Colon","Galeana","Madero"]
CONS="BCDFGHJKLMNPQRSTVWXYZ"; VOW="AEIOU"
def curp_falsa(r):
    pat=r.choice(P); mat=r.choice(M); nom=r.choice(N)
    L=lambda x: x if x.isalpha() else "X"
    v1=next((c for c in pat[1:] if c in VOW),"X")
    return f"{L(pat[0])}{v1}{L(mat[0])}{L(nom[0])}{r.randint(40,99)}{r.randint(1,12):02d}{r.randint(1,28):02d}{r.choice('HM')}{r.randint(1,32):02d}{r.choice(CONS)}{r.choice(CONS)}{r.choice(CONS)}{r.randint(0,9)}{r.randint(0,9)}"
a=argparse.ArgumentParser()
a.add_argument("--n",type=int,default=100000); a.add_argument("--cargar",action="store_true")
a.add_argument("--tabla",default="padron_sintetico"); a.add_argument("--salida",default=None)
A=a.parse_args(); r=random.Random(77)
u="http://localhost:8123/?user=default&password="+urllib.parse.quote(os.environ.get("CLICKHOUSE_PASSWORD",""),safe="")
def ch(url, body=None):
    if body is None: url, body = u, url
    urllib.request.urlopen(urllib.request.Request(url, data=body.encode() if isinstance(body,str) else body))
DDL=("CREATE TABLE IF NOT EXISTS qsoy."+A.tabla+" (cve UInt64, nombre String, paterno String, materno String, "
     "sexo String, edad UInt8, calle String, ext UInt16, colonia String, cp String, e UInt8, m UInt16, "
     "s UInt16, mza UInt8, curp String, latitud Float64, longitud Float64) ENGINE=MergeTree ORDER BY (e,s,cve)")
if A.cargar: ch(DDL); print(f"tabla qsoy.{A.tabla} lista")
t0=time.time(); buf=[]; f=open(A.salida,"w") if A.salida else None
def fila(i):
    e=r.randint(1,32); m=r.randint(1,125); s=r.randint(1,800)
    return f"{i}\t{r.choice(N)}\t{r.choice(P)}\t{r.choice(M)}\t{r.choice('HM')}\t{r.randint(18,90)}\t{r.choice(C)}\t{r.randint(1,900)}\tCol{r.randint(1,50)}{r.choice('ABC')}\t{r.randint(1,99):02d}{r.randint(100,999)}\t{e}\t{m}\t{s}\t{r.randint(1,20)}\t{curp_falsa(r)}\t{round(r.uniform(14.5,32.7),6)}\t{round(r.uniform(-117,-86.5),6)}"
for i in range(1,A.n+1):
    buf.append(fila(i))
    if len(buf)>=1_000_000:
        b="\n".join(buf)+"\n"
        if f: f.write(b)
        if A.cargar: ch(u+"&query="+urllib.parse.quote(f"INSERT INTO qsoy.{A.tabla} FORMAT TSV"), b)
        buf=[]
    if i%5_000_000==0: print(f"{i} filas... {time.time()-t0:.0f}s")
if buf:
    b="\n".join(buf)+"\n"
    if f: f.write(b)
    if A.cargar: ch(u+"&query="+urllib.parse.quote(f"INSERT INTO qsoy.{A.tabla} FORMAT TSV"), b)
if f: f.close()
print(f"OK {A.n} filas sinteticas en {time.time()-t0:.0f}s")
