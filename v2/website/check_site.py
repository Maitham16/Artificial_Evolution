#!/usr/bin/env python3
"""Validate the actual generated website, its project-prefix links and source hashes."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
BASE = 'https://maitham16.github.io/Artificial_Evolution/'


def verify(site):
    problems = []
    documents = {}
    for path in sorted(site.rglob('*.html')):
        relative = path.relative_to(site).as_posix()
        documents[relative] = BeautifulSoup(path.read_text(), 'html.parser')
    canonical_urls = set()
    links = 0
    for relative, soup in documents.items():
        url = BASE + (relative[:-10] if relative.endswith('index.html') else relative)
        if relative != '404.html':
            title = soup.find('title')
            description = soup.find('meta', attrs={'name': 'description'})
            canonical = soup.find('link', rel='canonical')
            if title is None or len(title.get_text(strip=True)) < 15:
                problems.append(f'{relative}: missing descriptive title')
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
            if image and image.get('content') != BASE + 'assets/gallery/living-world.jpg':
                problems.append(f'{relative}: wrong social image URL')
        for tag in soup.find_all(['a', 'img', 'script', 'link', 'source', 'video']):
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
                if target.fragment and local in documents:
                    fragment = unquote(target.fragment)
                    if not documents[local].find(id=fragment) and not documents[local].find(attrs={'name': fragment}):
                        problems.append(f'{relative}: missing anchor {raw}')
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
    return dict(ok=not problems, html_pages=len(documents), canonical_pages=len(canonical_urls),
                internal_links_checked=links, imported_sources=len(sources),
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
