from build_minna_import_2026_09 import *
for line in (DATA/'verbs.txt').read_text().splitlines():
 i,r,tr,group,h,j1,r1,j2,r2,j3,r3,notes=line.split('|')
 build(int(i),'Глаголы',r,tr,h,[j1,j2,j3],[r1,r2,r3],notes,['動詞',group])
