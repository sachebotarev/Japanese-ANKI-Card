from build_minna_import_2026_09 import *
for line in (DATA/'custom.txt').read_text().splitlines():
 i,t,r,tr,h,j1,r1,j2,r2,j3,r3,notes=line.split('|')
 tags={'Прилагательные_な':['ナ形容詞'],'Прилагательные_い':['イ形容詞'],'Наречия':['副詞']}.get(t,['名詞'])
 build(int(i),t,r,tr,h,[j1,j2,j3],[r1,r2,r3],notes,tags)
