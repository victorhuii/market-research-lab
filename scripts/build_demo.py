"""Build the public recorded-results demo. No training, raw data or model loading."""
from pathlib import Path
import argparse
import html
import json
import shutil
import sys

ROOT = next(p for p in Path(__file__).resolve().parents if (p/'deployment.json').is_file())
CSS = '''*{box-sizing:border-box}body{margin:0;background:#F8FAFC;color:#111827;font:16px/1.65 system-ui,sans-serif}main{max-width:1060px;margin:auto;padding:36px 24px 64px}a{color:#0F766E;text-underline-offset:3px}nav{display:flex;flex-wrap:wrap;gap:20px;margin-bottom:42px}h1{font-size:clamp(2rem,5vw,3.3rem);line-height:1.15;letter-spacing:-.04em;margin:12px 0 20px}h2{font-size:1.3rem;margin-top:38px}.tag{color:#0F766E;font-weight:650}.intro{max-width:800px;font-size:1.1rem}.notice{border-left:3px solid #0F766E;padding:12px 18px;background:white}figure{margin:30px 0}img{display:block;width:100%;height:auto;border:1px solid #d5dce4;border-radius:8px}figcaption,footer{font-size:.9rem;color:#475569;margin-top:10px}li{margin:12px 0}footer{border-top:1px solid #d5dce4;padding-top:20px;margin-top:42px}:focus-visible{outline:3px solid #0F766E;outline-offset:4px}.skip{position:absolute;left:-10000px}.skip:focus{left:20px;top:4px}'''
HEADERS = """/*
  Content-Security-Policy: default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Referrer-Policy: strict-origin-when-cross-origin
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Cache-Control: public, max-age=0, must-revalidate
"""

def build():
    config=json.loads((ROOT/'deployment.json').read_text())
    out=ROOT/config['output'];out.mkdir(parents=True,exist_ok=True)
    image=ROOT/config['image']
    if not image.is_file():raise ValueError('Recorded preview image is missing')
    if image.stat().st_size>25*1024*1024:raise ValueError('Preview exceeds the Pages asset limit')
    e=html.escape
    repo='https://github.com/victorhuii/'+config['repo']
    def doc(path):return repo+'/blob/main/'+path
    rows=''.join(f'<li><strong>{e(row[0])}.</strong> {e(row[1])} <em>{e(row[2])}</em></li>' for row in config['decisions'])
    page=f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="{e(config['summary'],quote=True)}"><title>{e(config['title'])} — recorded demo</title><link rel="stylesheet" href="style.css"></head>
<body><a class="skip" href="#main">Skip to content</a><main id="main"><nav aria-label="Project links"><a href="{repo}">Source code</a><a href="{doc(config['architecture'])}">Architecture</a><a href="{doc(config['deployment_doc'])}">Run and deploy</a><a href="https://github.com/victorhuii">All projects</a></nav>
<p class="tag">Recorded results demo</p><h1>{e(config['title'])}</h1><p class="intro">{e(config['summary'])}</p>
<p class="notice">This public demo presents existing project evidence. It does not execute the Python/C++ application, accept uploads, run new predictions or change saved state. <a href="{repo}#start">See the README for the full local application.</a></p>
<h2>Recorded evidence</h2><p>{e(config['evidence'])}</p><figure><img src="preview.png" alt="{e(config['title'])}: {e(config['image_kind'])}" loading="eager"><figcaption>{e(config['image_kind'])}. {e(config.get('image_credit',''))}</figcaption></figure>
<p><a href="{doc(config['portfolio'])}">Read the evaluation and implementation notes</a></p><h2>Design choices</h2><ul>{rows}</ul>
<h2>Scope and limits</h2><p>{e(config['limitation'])}</p><p><strong>Ownership:</strong> {e(config['ownership'])}. See the source repository for upstream and data attribution.</p>
<footer>Static portfolio demo · No accounts, data uploads or paid API calls · <a href="{doc(config['decisions_doc'])}">Full design rationale</a></footer></main></body></html>\n'''
    (out/'index.html').write_text(page)
    (out/'style.css').write_text(CSS+'\n')
    (out/'_headers').write_text(HEADERS)
    # Avoid Pages SPA fallback returning index.html for missing API/assets.
    (out/'404.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><title>Not found</title><h1>Page not found</h1><p>This is a recorded-results demo, with no backend API.</p><a href="./">Return to the demo</a></html>\n')
    shutil.copyfile(image,out/'preview.png')
    expected={'index.html','style.css','preview.png','_headers','404.html'}
    if {p.name for p in out.iterdir()}!=expected:raise ValueError('Unexpected output file; inspect before publishing')
    print('Built recorded demo:',config['output'])

if __name__=='__main__':build()
