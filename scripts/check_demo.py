"""Check a built static demo without browser or backend dependencies."""
from pathlib import Path
from html.parser import HTMLParser
import json
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'deployment.json').is_file())
config=json.loads((ROOT/'deployment.json').read_text());out=ROOT/config['output']
class Links(HTMLParser):
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key in ('src','href') and value and not value.startswith(('https://','#','data:','blob:')):
    target=out/value.split('#')[0]
    assert target.is_file() or (target.is_dir() and (target/'index.html').is_file()),value
Links().feed((out/'index.html').read_text())
assert (out/'404.html').is_file() and (out/'_headers').is_file()
for p in out.rglob('*'):
 if p.is_file():
  assert p.stat().st_size<=25*1024*1024,p
  assert p.suffix not in ('.pt','.pkl','.joblib','.sqlite','.db','.env','.py'),p
assert 'Content-Security-Policy:' in (out/'_headers').read_text()
assert 'nosniff' in (out/'_headers').read_text()
print('Static demo links, headers and artifact bounds passed')
