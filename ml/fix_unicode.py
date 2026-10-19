import sys, io
with open('build_phase5d_dataset.py','r',encoding='utf-8') as f:
    content = f.read()
# Replace remaining non-ASCII
content = content.replace(chr(8804), '<=')  # ≤
content = content.replace(chr(8805), '>=')  # ≥
content = content.replace(chr(177),  '+-')  # ±
content = content.replace(chr(215),  'x')   # ×
# Inject UTF-8 stdout at top if not already present
header = 'import sys, io\nsys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")\n'
if 'TextIOWrapper' not in content[:400]:
    content = header + content
with open('build_phase5d_dataset.py','w',encoding='utf-8') as f:
    f.write(content)
print('All Unicode fixed and UTF-8 stdout injected.')
