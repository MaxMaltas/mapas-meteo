from __future__ import annotations
import json
import sys
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.build_alert_zone_face_reference import _read_cap_snapshots
from meteo_pipeline.alert_map import _planar_faces,read_alert_shape

def graph(polys,precision):
    edge_faces=defaultdict(set)
    for i,poly in enumerate(polys):
        points=[tuple(round(x,precision) for x in p) for p in poly]
        if points[-1]!=points[0]:points.append(points[0])
        for a,b in zip(points,points[1:]):
            if a!=b:edge_faces[tuple(sorted((a,b)))].add(i)
    g=[set() for _ in polys]
    for fs in edge_faces.values():
        for i in fs:g[i].update(fs-{i})
    return g,edge_faces

def components(g):
    left=set(range(len(g)))
    result=[]
    while left:
        todo=[min(left)];seen=set(todo)
        while todo:
            i=todo.pop()
            for j in g[i]-seen:
                seen.add(j);todo.append(j)
        left-=seen;result.append(sorted(seen))
    return sorted(result,key=len,reverse=True)

def summary(g):
    return {'vertices':len(g),'edges':sum(map(len,g))//2,'degrees':dict(Counter(map(len,g))), 'component_sizes':list(map(len,components(g)))}

snapshots=_read_cap_snapshots(ROOT/'data/raw/2026-10-01/avisos_cap.data.tar')
sent,zones=max(((sent,{c:z for c,z in zs.items() if not c.endswith('C')}) for sent,zs in snapshots.items() if sum(len(z['polygons']) for c,z in zs.items() if not c.endswith('C'))==200),key=lambda a:a[0])
parts=[dict(code=c,name=z['name'],part=pi,poly=p) for c,z in sorted(zones.items()) for pi,p in enumerate(z['polygons'])]
faces=_planar_faces(read_alert_shape(ROOT/'data/alert_map_template/DOMDocument.xml','Capa_4'))
fg,fe=graph(faces,6)
print('FLA',summary(fg))
for precision in [6,5,4,3,2]:
    cg,ce=graph([p['poly'] for p in parts],precision)
    print('CAP',precision,summary(cg))
cg,ce=graph([p['poly'] for p in parts],4)
output={'sent':sent,'parts':parts,'faces':faces,'cap_neighbors':[sorted(n) for n in cg],'face_neighbors':[sorted(n) for n in fg]}
(ROOT/'output/topology_probe_graph.json').write_text(json.dumps(output,ensure_ascii=False),encoding='utf8')

pair_lengths=defaultdict(float)
for (a,b),fs in ce.items():
    for i in fs:
        for j in fs:
            if i<j:pair_lengths[i,j]+=math.dist(a,b)
print('SHORTEST CAP BOUNDARIES')
for (i,j),length in sorted(pair_lengths.items(),key=lambda x:x[1])[:45]:
    print(round(length,5),parts[i]['code'],parts[i]['part'],parts[i]['name'],'--',parts[j]['code'],parts[j]['part'],parts[j]['name'])
for threshold in [0,.015,.02,.025,.03,.04,.05,.075,.1]:
    print('CAP BOUNDARY THRESHOLD',threshold, 'edges remaining',sum(length>threshold for length in pair_lengths.values()))
