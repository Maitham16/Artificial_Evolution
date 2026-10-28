#!/usr/bin/env python3
"""Check tracked repository Markdown, example syntax and configuration coverage.

Website-owned pages use virtual source paths: validate their published links with
MkDocs strict mode and check_site.py, rather than treating those paths as files.
Run with the original project Python environment from any working directory.
"""
from pathlib import Path
import argparse,ast,json,re,subprocess,sys,urllib.parse,unicodedata
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'v2/backend'))
from dataclasses import fields
from research_session import RunConfig
from habitat import HabitatConfig
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--report',type=Path)
args=parser.parse_args()
tracked=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT,text=True).split('\0')
paths=[ROOT/name for name in tracked if name.endswith('.md') and not name.startswith('v2/website/pages/')]
virtual_pages=[name for name in tracked if name.startswith('v2/website/pages/') and name.endswith('.md')]
errors=[];counts={'markdown_files':len(paths),'relative_links':0,'anchors':0,'bash_blocks':0,'python_blocks':0,'json_blocks':0,'example_configs':0}
def anchors(p):
    data=re.sub(r'```.*?```','',p.read_text(),flags=re.S);seen={};result=set()
    for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$',data,re.M):
        heading=re.sub(r'\[([^]]+)\]\([^)]+\)',r'\1',heading).strip().lower()
        slug=''.join(c for c in heading if c in '-_ ' or unicodedata.category(c)[0] in 'LN').replace(' ','-')
        number=seen.get(slug,0);seen[slug]=number+1
        result.add(slug+(f'-{number}' if number else ''))
    result.update(re.findall(r'<a\s+(?:id|name)=["\']([^"\']+)',data))
    return result
for p in paths:
    text=p.read_text();blocks=list(re.finditer(r'^```([^\n]*)\n(.*?)^```\s*$',text,re.M|re.S))
    if text.count('\n```')%2:errors.append(f'{p.relative_to(ROOT)}: unbalanced fences')
    for match in blocks:
        lang,code=match[1].strip(),match[2]
        if lang in ('bash','sh'):
            counts['bash_blocks']+=1
            result=subprocess.run(['bash','-n'],input=code,text=True,capture_output=True)
            if result.returncode:errors.append(f'{p.name}: shell syntax: {result.stderr}')
        elif lang=='python':
            counts['python_blocks']+=1
            try:ast.parse(code)
            except SyntaxError as error:errors.append(f'{p.name}: Python syntax: {error}')
        elif lang=='json':
            counts['json_blocks']+=1
            try:RunConfig.from_dict(json.loads(code))
            except Exception as error:errors.append(f'{p.name}: JSON config: {error}')
    prose=re.sub(r'```.*?```','',text,flags=re.S)
    for raw in re.findall(r'\]\((<[^>\n]+>|[^()\s]+)(?:\s+"[^"]*")?\)',prose):
        raw=raw.strip('<>');url=urllib.parse.urlsplit(raw)
        if url.scheme or raw.startswith('//'):continue
        counts['relative_links']+=1
        destination=(p.parent/urllib.parse.unquote(url.path)).resolve() if url.path else p
        if not destination.exists():errors.append(f'{p.relative_to(ROOT)}: missing {raw}');continue
        if url.fragment and destination.suffix=='.md':
            counts['anchors']+=1
            if urllib.parse.unquote(url.fragment) not in anchors(destination):errors.append(f'{p.relative_to(ROOT)}: missing anchor {raw}')
for p in sorted((ROOT/'v2/docs/examples').glob('*.json')):
    RunConfig.load(p);counts['example_configs']+=1
reference=(ROOT/'v2/docs/CONFIGURATION.md').read_text()
for cls in (RunConfig,HabitatConfig):
    for f in fields(cls):
        if f'`{f.name}`' not in reference:errors.append(f'Missing config field: {cls.__name__}.{f.name}')
for file in ('v2/scripts/main.gd','v2/scripts/python_bridge.gd'):
    for flag in set(re.findall(r'"(--[a-z][a-z-]*)(?:=|"|\s)',(ROOT/file).read_text())):
        if flag=='--ready-file':continue
        if flag not in reference and flag not in ('--owner-pid','--export-root'):errors.append(f'Missing app flag: {flag}')
for file in sorted((ROOT/'v2').glob('*.command')):
    result=subprocess.run(['bash','-n',str(file)],capture_output=True,text=True)
    if result.returncode:errors.append(f'{file.name}: {result.stderr}')
record={'ok':not errors,'publication_pages_checked_by':'mkdocs build --strict and v2/website/check_site.py','virtual_source_pages':len(virtual_pages),'checks':counts,'RunConfig_fields':len(fields(RunConfig)),'HabitatConfig_fields':len(fields(HabitatConfig)),'problems':errors}
if args.report:
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
raise SystemExit(bool(errors))
