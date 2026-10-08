import json
import sys
import tarfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from meteo_pipeline.alerts import summarise_cap_by_zone

root = Path(__file__).resolve().parents[1]
geo_path = Path('C:/Users/Aruba IA/Downloads/geojson_1790910000.tar.gz')
cap_bytes = (root / 'data/raw/2026-10-02/avisos_cap.data.tar').read_bytes()
generated = json.loads((root / 'data/generated/2026-10-02/meteo.json').read_text(encoding='utf8'))
as_of = datetime.fromisoformat(generated['generated_at'])
# In AEMET's GeoJSON, 1=red, 2=orange, 3=yellow (inverse to severity rank).
levels = {0: 'green', 1: 'red', 2: 'orange', 3: 'yellow'}

geo = {}
with tarfile.open(geo_path) as archive:
    day_files = sorted(name for name in archive.getnames() if name.startswith('r_D+0_') and '20261002' in name)
    print('GeoJSON daily files:', *day_files, sep='\n  ')
    for name in day_files:
        document = json.load(archive.extractfile(name))
        print(name, 'features:', len(document['features']))
        for feature in document['features']:
            props = feature['properties']
            code = str(props['COD_Z']).upper()
            record = {'level': levels[int(props['Av_mayor'])], 'name': props['Nombre_zona'], 'geometry_type': feature['geometry']['type'], 'properties': props}
            if code in geo and geo[code]['level'] != record['level']:
                raise ValueError(f'Different daily levels for {code}')
            geo[code] = record

cap_all = {z['code']: z for z in summarise_cap_by_zone(cap_bytes, date(2026, 10, 2))['zones']}
cap_remain = {z['code']: z for z in summarise_cap_by_zone(cap_bytes, date(2026, 10, 2), as_of=as_of)['zones']}
print('GeoJSON levels:', Counter(z['level'] for z in geo.values()))
print('CAP full-day levels:', Counter(z['level'] for z in cap_all.values()))
print('CAP unexpired levels:', Counter(z['level'] for z in cap_remain.values()))
print('GeoJSON only:', sorted(set(geo)-set(cap_all)))
print('CAP only:', sorted(set(cap_all)-set(geo)))
for code in sorted(set(geo) | set(cap_all)):
    gl = geo.get(code, {}).get('level', 'green')
    al = cap_all.get(code, {}).get('level', 'green')
    rl = cap_remain.get(code, {}).get('level', 'green')
    if gl != al or gl != rl:
        print(code, geo.get(code, {}).get('name',cap_all.get(code, {}).get('name','')), 'geo', gl, 'cap_day', al, 'cap_remaining', rl)
