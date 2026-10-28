#!/usr/bin/env python3
"""Audit published pages, real media and external destinations without submitting URLs.

Use the isolated website environment after a strict MkDocs build. HTTP failures
caused by rate limits, authentication or network errors remain explicitly unverified.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from PIL import Image
import requests

from check_site import BASE, ROOT, verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def media_audit():
    folder = ROOT / 'v2/docs/media/gallery'
    manifest = json.loads((folder / 'captures.json').read_text())
    records = []
    for case in manifest['cases']:
        for kind in ('still', 'thumbnail', 'gif', 'video'):
            if kind not in case:
                continue
            info = case[kind]
            path = folder / info['file']
            assert sha(path) == info['sha256'], path
            assert path.stat().st_size == info['bytes'], path
            if kind != 'video':
                with Image.open(path) as picture:
                    assert picture.size == (info['width'], info['height']), path
                    if kind == 'gif':
                        assert picture.n_frames == info['frames'], path
                    for index in range(getattr(picture, 'n_frames', 1)):
                        picture.seek(index)
                        picture.load()
            else:
                assert b'ftyp' in path.read_bytes()[:32], path
            records.append(dict(file=info['file'], kind=kind, bytes=info['bytes'], sha256=info['sha256']))
    social = ROOT / 'v2/website/pages/assets/social'
    provenance = json.loads((social / 'provenance.json').read_text())
    assert sha(ROOT / provenance['screenshot']['path']) == provenance['screenshot']['sha256']
    assert sha(social / 'social-preview.jpg') == provenance['output']['sha256']
    assert sha(social / 'social-preview.svg') == provenance['svg_sha256']
    return dict(ok=True, cases=len(manifest['cases']), checked_files=len(records),
                source='Existing native application captures; byte integrity and image decoding checked',
                social_card_provenance=True, files=records)


def response(url):
    result = requests.get(url, timeout=(8, 25))
    result.raise_for_status()
    return result


def live_audit(site):
    local = ET.parse(site / 'sitemap.xml')
    expected = {e.text for e in local.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    remote = ET.fromstring(response(BASE + 'sitemap.xml').content)
    urls = {e.text for e in remote.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc')}
    assert urls == expected, 'Live sitemap differs from the current strict build'

    def page(url):
        result = response(url)
        soup = BeautifulSoup(result.text, 'html.parser')
        assert soup.find('link', rel='canonical')['href'] == url, url
        assert soup.find('meta', attrs={'property': 'og:url'})['content'] == url, url
        assert soup.find('meta', attrs={'property': 'og:image'})['content'] == BASE + 'assets/social/social-preview.jpg', url
        assert soup.find('meta', attrs={'name': 'description'})['content'], url
        robots = soup.find('meta', attrs={'name': 'robots'})
        assert not robots or 'noindex' not in robots.get('content', '').lower(), url
        assert 'noindex' not in result.headers.get('X-Robots-Tag', '').lower(), url
        return dict(url=url, status=result.status_code, title=soup.title.get_text(strip=True))

    with ThreadPoolExecutor(max_workers=6) as pool:
        pages = list(pool.map(page, sorted(urls)))
    # Check every published gallery file against its original bytes, including MP4s.
    gallery = json.loads((ROOT / 'v2/docs/media/gallery/captures.json').read_text())
    assets = [info for case in gallery['cases'] for key in ('still', 'thumbnail', 'gif', 'video')
              if (info := case.get(key))]

    def asset(info):
        try:
            data = response(BASE + 'assets/gallery/' + info['file']).content
            matched = hashlib.sha256(data).hexdigest() == info['sha256']
            return dict(file=info['file'], bytes=len(data), sha256_matches=matched, ok=matched)
        except requests.RequestException as error:
            return dict(file=info['file'], ok=False, error=str(error))

    with ThreadPoolExecutor(max_workers=4) as pool:
        asset_results = list(pool.map(asset, assets))
    downloaded_bytes = sum(item.get('bytes', 0) for item in asset_results)
    card = ROOT / 'v2/website/pages/assets/social/social-preview.jpg'
    assert response(BASE + 'assets/social/social-preview.jpg').content == card.read_bytes()
    sources = response(BASE + 'source-manifest.json').json()['pages']
    for item in sources.values():
        assert sha(ROOT / item['source']) == item['sha256'], item['source']
    index = response(BASE + 'search/search_index.json').json()
    assert len(index['docs']) >= len(pages)
    home = BeautifulSoup(response(BASE).text, 'html.parser')
    tokens = [tag['name'] for tag in home.find_all('meta', attrs={'name': ['google-site-verification', 'msvalidate.01']})]
    host_robots = requests.get(urljoin(BASE, '/robots.txt'), timeout=20)
    return dict(ok=all(item['ok'] for item in asset_results), pages=pages, sitemap_urls=len(urls), gallery_downloads=len(assets),
                gallery_download_bytes=downloaded_bytes, imported_source_hashes=len(sources),
                gallery_results=asset_results,
                search_entries=len(index['docs']), social_card_matches_source=True,
                host_root_robots_status=host_robots.status_code, configured_verification_tag_names=tokens,
                search_indexing='Unverified: no authenticated Google/Bing indexing evidence inspected')


def external_audit(site):
    urls = set()
    for path in site.rglob('*.html'):
        soup = BeautifulSoup(path.read_text(), 'html.parser')
        for tag in soup.find_all(['a', 'img', 'script', 'link']):
            raw = tag.get('href') or tag.get('src', '')
            parsed = urlsplit(raw)
            if parsed.scheme in ('http', 'https') and parsed.netloc != urlsplit(BASE).netloc:
                urls.add(raw.split('#', 1)[0])
    tracked = set(subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT, text=True).split('\0'))
    local_paths, remote_urls, missing = [], [], []
    for url in sorted(urls):
        path = unquote(urlsplit(url).path)
        if urlsplit(url).netloc == 'github.com' and any(path.startswith('/Maitham16/Artificial_Evolution/' + kind + '/master/') for kind in ('blob', 'tree')):
            _, _, _, kind, _, relative = path.split('/', 5)
            exists = relative in tracked if kind == 'blob' else any(p.startswith(relative.rstrip('/') + '/') for p in tracked)
            (local_paths if exists else missing).append(url)
        else:
            remote_urls.append(url)

    def check(url):
        try:
            with requests.get(url, stream=True, timeout=(6, 15), headers={'Range': 'bytes=0-2047'}) as result:
                status = result.status_code
                category = ('reachable' if status < 400 else 'broken' if status in (404, 410)
                            else 'access_limited' if status in (401, 403, 429) else 'unverified')
                return dict(url=url, status=status, final_url=result.url.split('?', 1)[0], classification=category)
        except requests.RequestException as error:
            return dict(url=url, status=None, classification='unverified', error=type(error).__name__)

    with ThreadPoolExecutor(max_workers=6) as pool:
        http = list(pool.map(check, remote_urls))
    return dict(unique_urls=len(urls), repository_paths_verified=len(local_paths),
                missing_repository_paths=missing, http_results=http,
                note='Master blob/tree paths checked against tracked files; rate-limited or blocked endpoints are not asserted broken or indexed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, default=ROOT / '.cache/website/site')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--external', action='store_true')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = dict(local=verify(args.site), media=media_audit())
    if args.live:
        report['live'] = live_audit(args.site)
    if args.external:
        report['external'] = external_audit(args.site)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: {name: value for name, value in data.items()
                         if name not in ('pages', 'files', 'http_results', 'gallery_results')}
                      for k, data in report.items()}, indent=2))
    broken = report.get('external', {}).get('missing_repository_paths', [])
    broken += [item['url'] for item in report.get('external', {}).get('http_results', []) if item['classification'] == 'broken']
    raise SystemExit(not report['local']['ok'] or not report.get('live', {'ok': True})['ok'] or bool(broken))


if __name__ == '__main__':
    main()
