from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw, ImageFont

from meteo_pipeline.alert_map import _planar_faces, read_alert_shape


root = Path(__file__).resolve().parents[1]
faces = _planar_faces(read_alert_shape(root / 'data/alert_map_template/DOMDocument.xml', 'Capa_4'))
image = Image.new('RGB', (1920, 1080), '#20252a')
draw = ImageDraw.Draw(image)
try:
    font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 15)
except OSError:
    font = ImageFont.load_default()

for face in faces:
    draw.polygon(face, fill='#d8e4e8', outline='#3e525a', width=2)
for index, face in enumerate(faces):
    closed = face if face[0] == face[-1] else face + [face[0]]
    area = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(closed, closed[1:]):
        cross = x1 * y2 - x2 * y1
        area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(area) > 1e-9:
        x, y = cx / (3 * area), cy / (3 * area)
    else:
        x = sum(point[0] for point in face) / len(face)
        y = sum(point[1] for point in face) / len(face)
    text = str(index)
    bounds = draw.textbbox((0, 0), text, font=font)
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    draw.rectangle((x-width/2-2, y-height/2-2, x+width/2+2, y+height/2+2), fill='#ffffff')
    draw.text((x-width/2, y-height/2), text, fill='#111111', font=font)

path = root / 'output' / 'face_audit_atlas.png'
image.save(path)
print(path)
