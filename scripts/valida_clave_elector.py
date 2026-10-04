#!/usr/bin/env python3
import os
# valida_clave_elector.py v2 - PRE-validacion de formato de clave de elector (18 posiciones)
# Heuristica: 6 letras + YYMMDD + [HM] + entidad(2) + secuencia/DV(3).
# La validacion DEFINITIVA contra padron solo la hace el instituto (DV oficial).
import re, sys, datetime
REGEX=r'[A-ZÑ]{6}\d{6}[HM]\d{5}'
def valida(cl):
    cl=(cl or '').upper().strip()
    if not re.fullmatch(REGEX,cl): return False,'formato: 6 letras + AAMMDD + H/M + entidad(2) + seq/DV(3) = 18 pos'
    a,m,d=int(cl[6:8]),int(cl[8:10]),int(cl[10:12])
    yy=datetime.date.today().year%100
    year=2000+a if a<=yy+1 else 1900+a
    try: datetime.date(year,m,d)
    except ValueError: return False,'fecha de nacimiento invalida'
    if not (1<=int(cl[13:15])<=32): return False,'entidad fuera de rango 01-32'
    return True,'ok'
def selftest():
    casos=[('SLPMRA850414H06409',True),('SLPMRA850414X06409',False),('SLPMRA850414H0640',False),
           ('SLPMRA851301H06409',False),('SLPMRA850414H99409',False)]
    mal=0
    for c,exp in casos:
        ok,msg=valida(c)
        print(('OK  ' if ok else 'BAD '),c,'(esperado',('OK' if exp else 'BAD'),'-',msg+')')
        if ok!=exp: mal+=1
    print('selftest:','PASS 5/5' if mal==0 else f'FAIL {mal} casos')
    return 1 if mal else 0
if __name__=='__main__':
    if '--selftest' in sys.argv: sys.exit(selftest())
    if len(sys.argv)==1: print('uso: valida_clave_elector.py CLAVE1 [...] | --selftest'); sys.exit(0)
    bad=0
    for c in sys.argv[1:]:
        ok,msg=valida(c); print(('OK  ' if ok else 'BAD '),c,'->',msg); bad+=(0 if ok else 1)
    sys.exit(1 if bad else 0)
