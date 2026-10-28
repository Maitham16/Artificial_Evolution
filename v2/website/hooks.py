"""Publish existing Markdown as virtual MkDocs files; never edit its sources."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from mkdocs.structure.files import File
from PIL import Image
import yaml

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'https://github.com/Maitham16/Artificial_Evolution'
SPECIAL = {
    'README.md': 'v1/research-record.md',
    'v2/README.md': 'v2/index.md',
    'docs/USER_GUIDE.md': 'v1/user-guide.md',
    'docs/REPRODUCIBILITY.md': 'v1/reproducibility.md',
    'docs/RELEASE-v1.0.1.md': 'v1/releases/v1.0.1.md',
    'docs/RELEASE-v1.0.0.md': 'v1/releases/v1.0.0.md',
    'v2/docs/README.md': 'v2/documentation.md',
    'v2/docs/GALLERY.md': 'gallery/index.md',
    'v2/docs/ARCHITECTURE.md': 'architecture/index.md',
    'v2/docs/DEVELOPMENT.md': 'development/application.md',
    'v2/docs/RESEARCH_AND_VALIDATION.md': 'research/validation.md',
}
DESCRIPTIONS = {
    'INSTALLATION': 'Install and launch the Godot 3D Living World on macOS, prepare Python and Godot for source development, or keep running the original 2D simulator.',
    'USER_GUIDE': 'Learn the cameras, trackpad gestures, creature inspection, research panels, pause, speed and export controls in Artificial Evolution 2.0.',
    'SIMULATION_MODES': 'Explore seven Python ecological modes: food seeking, seasons, hazards, inherited bodies, predator–prey, social groups and continuous reproduction.',
    'ANIMALS_AND_ANIMATION': 'Understand deer and wolf models, skeletal actions, real Python event triggers, growth, terrain foot IK, asset licenses and animation limitations.',
    'ENVIRONMENTS': 'Choose food layouts and understand the landscape, seasons, weather, daylight and the difference between decorative scenery and actual simulation rules.',
    'EVOLUTION_AND_BRAINS': 'Learn how sensory inputs, NumPy neural controllers, fitness, inheritance, mutation and selection drive the preserved Python simulation.',
    'PHYSICAL_HABITAT': 'Enable the optional Python terrain, wading and climate extension, inspect its energy costs and replay its explicitly recorded 2.5D rules.',
    'CONFIGURATION': 'Find every simulation and physical-habitat configuration field, quality profile, application setting and supported command-line option.',
    'EXPORTS_AND_REPLAY': 'Export configurations, datasets, genomes, plots and reports; verify original-rule and physical-habitat runs with the appropriate numerical replay.',
    'GALLERY': 'View 14 real application screenshots and five short recordings of landscapes, animals, controls, all seven modes and the original 2D simulator.',
    'ARCHITECTURE': 'Trace the Godot desktop, local Python bridge and original numerical engine; understand snapshots, interpolation, event ownership and exports.',
    'DEVELOPMENT': 'Develop and test Artificial Evolution 2.0, author Blender assets, build the Mac application and verify original-source preservation.',
    'TROUBLESHOOTING': 'Resolve startup, permissions, Python connection, rendering, panel input, performance, export and numerical replay issues in the 3D application.',
    'RESEARCH_AND_VALIDATION': 'Interpret fitness, survival, meals, ancestry and genetic diversity, with matched baselines, independent seeds and explicit research limitations.',
}
ASSET_SOURCES = {}
PUBLISHED_SOURCES = {}


def source_pages():
    result = {ROOT / name: uri for name, uri in SPECIAL.items()}
    for source in sorted((ROOT / 'v2/docs').rglob('*.md')):
        if source in result:
            continue
        relative = source.relative_to(ROOT / 'v2/docs')
        slug = source.stem.lower().replace('_', '-')
        if len(relative.parts) == 1:
            uri = f'v2/{slug}.md'
        else:
            parent = relative.parent.as_posix()
            uri = f'v2/records/{parent}/' + ('index.md' if source.name == 'README.md' else slug + '.md')
        result[source] = uri
    return result


def archived_v1(text):
    start, end = '<!-- V1-README-ARCHIVE:START -->\n', '<!-- V1-README-ARCHIVE:END -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('The uniquely delimited original V1 README is required')
    return text.split(start, 1)[1].split(end, 1)[0]


def asset_uri(source):
    relative = source.relative_to(ROOT).as_posix()
    if relative.startswith('v2/docs/media/gallery/'):
        return 'assets/gallery/' + source.name
    return 'assets/original/' + relative


def rewrite_url(raw, source, uri, mapping, files, config):
    url = urlsplit(raw)
    if url.scheme or url.netloc or not url.path or raw.startswith('/'):
        return raw
    target = (source.parent / unquote(url.path)).resolve()
    if not target.is_relative_to(ROOT):
        raise ValueError(f'Link escapes repository: {source}: {raw}')
    if target in mapping:
        route = mapping[target]
        if source == ROOT / 'v2/README.md' and target == ROOT / 'README.md' and not url.fragment:
            route = 'index.md'
    elif target.is_file() and (target.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.mp4', '.svg'}
                              or 'v2/docs/examples/' in target.as_posix()
                              or target == ROOT / 'v2/docs/media/gallery/captures.json'):
        route = asset_uri(target)
        if route not in ASSET_SOURCES:
            ASSET_SOURCES[route] = target
            files.append(File.generated(config, route, abs_src_path=str(target)))
    else:
        relative = quote(target.relative_to(ROOT).as_posix(), safe='/')
        kind = 'tree' if target.is_dir() or url.path.endswith('/') else 'blob'
        return urlunsplit(('https', 'github.com', '/Maitham16/Artificial_Evolution/' + kind + '/master/' + relative,
                           url.query, url.fragment))
    relative = posixpath.relpath(route, str(PurePosixPath(uri).parent))
    return urlunsplit(('', '', relative, url.query, url.fragment))


def rewrite_markdown(text, source, uri, mapping, files, config):
    # Fenced examples are commands/configuration, not navigation. Keep them intact.
    blocks = re.split(r'(^[ \t]*```[^\n]*\n.*?^[ \t]*```[^\n]*$)', text, flags=re.M | re.S)
    pattern = re.compile(r'\]\((<[^>\n]+>|[^\s)]+)([^)]*)\)')
    for index in range(0, len(blocks), 2):
        def replace(match):
            url = match[1].strip('<>')
            rewritten = rewrite_url(url, source, uri, mapping, files, config)
            return '](' + ('<' + rewritten + '>' if ' ' in rewritten else rewritten) + match[2] + ')'
        blocks[index] = pattern.sub(replace, blocks[index])
        blocks[index] = re.sub(r'((?:href|src)=")[^"]+(?=")',
            lambda m: m[1] + rewrite_url(m[0][len(m[1]):], source, uri, mapping, files, config), blocks[index])
    text = ''.join(blocks)
    # Enable standard Markdown inside the GitHub-oriented HTML wrappers, in this copy only.
    return text.replace('<details>', '<details markdown="1">').replace('<div align="center">', '<div align="center" markdown="1">')


def on_files(files, config):
    ASSET_SOURCES.clear()
    PUBLISHED_SOURCES.clear()
    mapping = source_pages()
    for source, uri in mapping.items():
        original = source.read_text()
        text = archived_v1(original) if source == ROOT / 'README.md' else original
        title = re.search(r'^#\s+(.+)$', text, re.M)[1].strip()
        if uri.startswith('v2/') and not title.startswith('Artificial Evolution'):
            title = 'V2 · ' + title
        elif uri.startswith('v1/'):
            title = 'V1 · ' + title
        if uri == 'v1/research-record.md':
            title = 'V1 · Complete research record, Steps 1–28'
        elif uri == 'v2/index.md':
            title = 'Godot 3D ecosystem simulator · V2'
        description = DESCRIPTIONS.get(source.stem,
            f'{title}. Read the original project guide, implementation details and recorded evidence for Artificial Evolution.')
        if source == ROOT / 'docs/USER_GUIDE.md':
            description = 'Use the original Python/Pygame research workbench: seven worlds, studies, controls, live plots, ancestry, exports and reproducible numerical replay.'
        metadata = dict(title=title, description=description,
                        source_url=REPOSITORY + '/blob/master/' + source.relative_to(ROOT).as_posix())
        if uri.startswith('v2/records/'):
            metadata['search'] = dict(boost=0.5)
        body = rewrite_markdown(text, source, uri, mapping, files, config)
        if uri == 'v1/research-record.md':
            body = '!!! note "Preserved V1 scientific record"\n    This is the complete original README. Step-specific counts, results and release statements describe their recorded revisions.\n\n' + body
        files.append(File.generated(config, uri, content='---\n' + yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True) + '---\n\n' + body))
        PUBLISHED_SOURCES[uri] = dict(source=source.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(source.read_bytes()).hexdigest())
    links = ['# Engineering records\n\nRecorded audits describe the build, machine and conditions they measured. They do not retroactively validate every later revision.\n']
    for source, uri in sorted(mapping.items()):
        if source.name == 'README.md' and '/records/' in uri:
            title = source.parent.name.replace('-', ' ').title()
            links.append(f'- [{title}]({posixpath.relpath(uri, "research")})')
    files.append(File.generated(config, 'research/engineering.md', content='---\ntitle: Engineering audits and recorded validation\ndescription: Browse preserved native rendering, animation, Python bridge, desktop packaging, physical habitat and source-preservation audits.\n---\n\n' + '\n'.join(links)))
    icon = ROOT / 'v2/assets/icon.svg'
    files.append(File.generated(config, 'assets/brand/icon.svg', abs_src_path=str(icon)))
    files.append(File.generated(config, 'assets/LICENSE.txt', abs_src_path=str(ROOT / 'LICENSE')))
    return files


@lru_cache(maxsize=256)
def image_dimensions(source):
    if source.suffix.lower() == '.svg':
        return None
    with Image.open(source) as picture:
        return picture.size


def on_page_content(html, page, config, files):
    soup = BeautifulSoup(html, 'html.parser')
    # Prefer explicit playback over loading looping GIFs on the website.
    for anchor in soup.find_all('a'):
        image = anchor.find('img')
        if image and image.get('src', '').endswith('.gif') and anchor.get('href', '').endswith('.mp4'):
            video = soup.new_tag('video', controls='', preload='none', playsinline='',
                                 poster=image['src'][:-4] + '.jpg', attrs={'class': 'ae-video', 'aria-label': image.get('alt', 'Actual application recording')})
            video.append(soup.new_tag('source', src=anchor['href'], type='video/mp4'))
            fallback = soup.new_tag('a', href=anchor['href'])
            fallback.string = 'Download the actual application recording (MP4)'
            video.append(fallback)
            anchor.replace_with(video)
    for image in soup.find_all('img'):
        image['decoding'] = 'async'
        hero = page.is_homepage and image.get('src', '').endswith('/living-world.jpg')
        image['loading'] = 'eager' if hero else 'lazy'
        if hero:
            image['fetchpriority'] = 'high'
        path = unquote(urlsplit(urljoin('https://site.invalid/' + page.url, image.get('src', ''))).path).lstrip('/')
        source = ASSET_SOURCES.get(path)
        if source:
            size = image_dimensions(source)
            if size:
                image['width'], image['height'] = str(size[0]), str(size[1])
    return str(soup)


def on_post_build(config):
    site = Path(config.site_dir)
    (site / '.nojekyll').write_text('')
    (site / 'source-manifest.json').write_text(json.dumps(dict(
        description='Documentation sources are read without editing them; links, metadata and web presentation are adapted only in generated pages.',
        pages=PUBLISHED_SOURCES), indent=2) + '\n')
