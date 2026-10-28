#!/usr/bin/env python3
"""Validate the actual generated website, its project-prefix links and source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://maitham16.github.io/Artificial_Evolution/'


def verify(site):
    problems = []
    documents = {}
    for path in sorted(site.rglob('*.html')):
        relative = path.relative_to(site).as_posix()
        documents[relative] = BeautifulSoup(path.read_text(), 'html.parser')
    canonical_urls = set()
    titles = set()
    graph = {name: set() for name in documents}
    links = 0
    for relative, soup in documents.items():
        url = BASE + (relative[:-10] if relative.endswith('index.html') else relative)
        if relative != '404.html':
            title = soup.find('title')
            description = soup.find('meta', attrs={'name': 'description'})
            canonical = soup.find('link', rel='canonical')
            if title is None or len(title.get_text(strip=True)) < 15:
                problems.append(f'{relative}: missing descriptive title')
            elif title.get_text().count('Artificial Evolution') > 1:
                problems.append(f'{relative}: repeated project branding in page title')
            if title:
                value = title.get_text(strip=True)
                if value in titles:
                    problems.append(f'{relative}: duplicate page title')
                titles.add(value)
            if description is None or len(description.get('content', '')) < 50:
                problems.append(f'{relative}: missing descriptive metadata')
            if canonical is None or canonical.get('href') != url:
                problems.append(f'{relative}: wrong canonical URL (expected {url})')
            else:
                canonical_urls.add(url)
            for property in ('og:title', 'og:description', 'og:image', 'og:url'):
                tag = soup.find('meta', attrs={'property': property})
                if not tag or not tag.get('content'):
                    problems.append(f'{relative}: missing {property}')
            image = soup.find('meta', attrs={'property': 'og:image'})
            if image and image.get('content') != BASE + 'assets/social/social-preview.jpg':
                problems.append(f'{relative}: wrong social image URL')
            for property, expected in (('og:image:width', '1280'), ('og:image:height', '640')):
                tag = soup.find('meta', attrs={'property': property})
                if not tag or tag.get('content') != expected:
                    problems.append(f'{relative}: wrong {property}')
        for tag in soup.find_all(['a', 'img', 'script', 'link', 'source', 'video']):
            if tag.name == 'img' and not tag.has_attr('alt'):
                problems.append(f'{relative}: image has no alt attribute')
            raw = tag.get('href') if tag.name in ('a', 'link') else tag.get('src')
            values = [raw]
            if tag.name == 'video':
                values.append(tag.get('poster'))
                if tag.get('preload') != 'none' or tag.has_attr('autoplay'):
                    problems.append(f'{relative}: gallery video must load only on explicit playback')
            for raw in values:
                if not raw:
                    continue
                target = urlsplit(urljoin(url, raw))
                if target.scheme not in ('http', 'https') or target.netloc != urlsplit(BASE).netloc:
                    continue
                prefix = urlsplit(BASE).path
                if not target.path.startswith(prefix):
                    problems.append(f'{relative}: URL escapes project prefix: {raw}')
                    continue
                local = unquote(target.path[len(prefix):])
                if not local or local.endswith('/'):
                    local += 'index.html'
                destination = site / local
                links += 1
                if not destination.is_file():
                    problems.append(f'{relative}: missing {raw}')
                    continue
                if tag.name == 'a' and local in documents:
                    graph[relative].add(local)
                if target.fragment and local in documents:
                    fragment = unquote(target.fragment)
                    if not documents[local].find(id=fragment) and not documents[local].find(attrs={'name': fragment}):
                        problems.append(f'{relative}: missing anchor {raw}')
    reached, pending = set(), ['index.html']
    while pending:
        current = pending.pop()
        if current not in reached:
            reached.add(current)
            pending.extend(graph[current] - reached)
    for name in documents.keys() - reached - {'404.html'}:
        problems.append(f'{name}: unreachable through links from homepage')
    # Check all manifest outputs, including previews not embedded in Markdown.
    gallery = json.loads((ROOT / 'v2/docs/media/gallery/captures.json').read_text())
    gallery_outputs = 0
    for case in gallery['cases']:
        for kind in ('still', 'thumbnail', 'gif', 'video'):
            if kind not in case:
                continue
            item = case[kind]
            output = site / 'assets/gallery' / item['file']
            gallery_outputs += 1
            if not output.is_file():
                problems.append(f'Gallery manifest output missing: {item["file"]}')
            elif hashlib.sha256(output.read_bytes()).hexdigest() != item['sha256']:
                problems.append(f'Gallery output differs from capture: {item["file"]}')
    sitemap = site / 'sitemap.xml'
    urls = {e.text for e in ET.parse(sitemap).findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    if urls != canonical_urls:
        problems.append('Sitemap/canonical mismatch: ' + repr(sorted(urls.symmetric_difference(canonical_urls))))
    if BASE + 'sitemap.xml' not in (site / 'robots.txt').read_text():
        problems.append('robots.txt: missing production sitemap reference')
    index = json.loads((site / 'search/search_index.json').read_text())
    if len(index['docs']) < len(documents) - 1:
        problems.append('Search index is missing published content')
    sources = json.loads((site / 'source-manifest.json').read_text())['pages']
    for uri, record in sources.items():
        if hashlib.sha256((ROOT / record['source']).read_bytes()).hexdigest() != record['sha256']:
            problems.append(f'{uri}: original documentation source changed during build')
    if not (site / '.nojekyll').is_file():
        problems.append('Missing .nojekyll for GitHub Pages artifact')
    social = site / 'assets/social/social-preview.jpg'
    with Image.open(social) as image:
        if image.size != (1280, 640) or social.stat().st_size >= 1_000_000:
            problems.append('Social preview must be 1280x640 and under 1 MB')
    schemas = [json.loads(tag.string) for tag in documents['index.html'].find_all('script', type='application/ld+json')]
    if not any(schema.get('@type') == 'SoftwareSourceCode'
               and schema.get('codeRepository') == 'https://github.com/Maitham16/Artificial_Evolution' for schema in schemas):
        problems.append('Homepage is missing accurate source-repository structured data')
    # Verification fields are opt-in: a fresh build must not claim fictitious ownership.
    for tag in documents['index.html'].find_all('meta', attrs={'name': ['google-site-verification', 'msvalidate.01']}):
        if not tag.get('content') or tag['content'] in ('YOUR_TOKEN', 'TODO', 'placeholder'):
            problems.append('Invalid placeholder search-engine verification token')
    return dict(ok=not problems, html_pages=len(documents), canonical_pages=len(canonical_urls),
                internal_links_checked=links, imported_sources=len(sources),
                reachable_content_pages=len(reached - {'404.html'}), gallery_outputs=gallery_outputs,
                search_entries=len(index['docs']), sitemap_urls=len(urls), problems=problems)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT / '.cache/website/site')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify(args.site.resolve())
    encoded = json.dumps(result, indent=2) + '\n'
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded)
    print(encoded, end='')
    raise SystemExit(not result['ok'])


if __name__ == '__main__':
    main()
