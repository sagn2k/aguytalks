#!/usr/bin/env python3
"""
Build A Guy Talks into a single self-contained index.html.

Pulls the essays live from Substack, embeds the fonts, and picks up any
photos dropped into photos/ (see photos/HOW-TO.txt for the naming).
Missing photos degrade to reserved plates instead of breaking.

    python3 build.py
"""

import base64, collections, html, io, json, os, subprocess, sys, tempfile, urllib.request

HERE    = os.path.dirname(os.path.abspath(__file__))
DIST    = os.path.join(HERE, 'docs')   # GitHub Pages serves main:/docs
SPLIT   = '--dist' in sys.argv        # real files for a real domain
# CNAME only once DNS is actually pointed here; until then it would make
# GitHub redirect the github.io preview to a domain that does not resolve.
LIVE    = '--domain' in sys.argv
PHOTOS  = os.path.join(HERE, 'photos')
ASSETS  = os.path.join(HERE, 'assets')
UA      = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0 Safari/537.36'
ARCHIVE = 'https://aguytalks.substack.com/api/v1/archive?sort=new&limit=50&offset=0'
DOMAIN  = 'aguytalks.com'

DEPT = {
    'creative-rut-rut-creative-rotten':   'Criticism',
    'modis-india-is-what-george-orwell':  'Politics',
    'alone-at-26-paris':                  'Dispatch',
    'beyond-the-white-gaze':              'Race & Fashion',
    'a-short-thesis-on-those-dior-charms':'Runway',
    'fuck-the-fashion-archives':          'Manifesto',
    'martin-margiela-probably-hates-the': 'Archive',
    'against-the-cult-of-personal-style': 'Theory',
    'jesus-is-lord-and-so-is-riccardo':   'Runway',
}

TAG_FIX = {
    'criticisim':'Criticism', 'culture theory essay':'Culture Theory',
    'anthropology essay':'Anthropology', 'art & visual culture':'Art &amp; Visual Culture',
    'fashion essay':'Fashion', 'archival fashion':'Archival Fashion',
    'political science':'Politics', 'fashion week':'Fashion Week',
}



# ---------------------------------------------------------------- helpers

def b64(path):
    with open(path, 'rb') as f:
        return base64.b64encode(f.read()).decode()


def prep_image(src, max_px=1400, quality=64):
    """Resize + JPEG-compress via macOS sips. Returns base64, or None."""
    out = os.path.join(tempfile.gettempdir(), 'agt_' + str(abs(hash(src))) + '.jpg')
    r = subprocess.run(
        ['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', str(quality),
         '-Z', str(max_px), src, '--out', out],
        capture_output=True)
    if r.returncode != 0 or not os.path.exists(out):
        print('  ! could not process %s' % os.path.basename(src), file=sys.stderr)
        return None
    return b64(out)


def asset(name, data_b64, mime='image/jpeg'):
    """Inline as a data URI, or write a real file and return its path."""
    if not SPLIT:
        return 'data:%s;base64,%s' % (mime, data_b64)
    sub = 'fonts' if mime.startswith('font') else 'img'
    d = os.path.join(DIST, sub)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), 'wb') as f:
        f.write(base64.b64decode(data_b64))
    return '%s/%s' % (sub, name)


def find_photo(stem):
    """First photos/<stem>.<ext> that exists."""
    for ext in ('jpg', 'jpeg', 'png', 'heic', 'webp', 'JPG', 'JPEG', 'PNG', 'HEIC'):
        p = os.path.join(PHOTOS, '%s.%s' % (stem, ext))
        if os.path.exists(p):
            return p
    return None


def look_captions(n):
    """photos/captions.txt, one caption per line, in look-N order.
    Missing or short -> 'Plate NN', so photos never arrive mislabelled."""
    path = os.path.join(PHOTOS, 'captions.txt')
    lines = []
    if os.path.exists(path):
        lines = [l.strip() for l in io.open(path, encoding='utf-8').read().split('\n')]
        lines = [l for l in lines if l and not l.startswith('#')]
    return [lines[i] if i < len(lines) else 'Plate %02d' % (i + 1) for i in range(n)]


def find_looks():
    """photos/look-N.* sorted numerically."""
    if not os.path.isdir(PHOTOS):
        return []
    out = []
    for name in os.listdir(PHOTOS):
        stem, dot, ext = name.rpartition('.')
        if not stem.lower().startswith('look-') or ext.lower() not in (
                'jpg', 'jpeg', 'png', 'heic', 'webp'):
            continue
        try:
            n = int(stem.split('-', 1)[1])
        except (ValueError, IndexError):
            continue
        out.append((n, os.path.join(PHOTOS, name)))
    return [p for _, p in sorted(out)]


def roman(n):
    vals=[(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')]
    out=''
    for v,r in vals:
        while n>=v: out+=r; n-=v
    return out


# ---------------------------------------------------------------- content

def fetch_archive():
    cache = os.path.join(HERE, 'archive.json')
    try:
        req = urllib.request.Request(ARCHIVE, headers={'User-Agent': UA})
        data = json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
        with open(cache, 'w') as f:
            json.dump(data, f)
        return data
    except Exception as e:
        if os.path.exists(cache):
            print('  ! Substack unreachable (%s), using cached archive' % e, file=sys.stderr)
            return json.load(open(cache))
        raise


def build_toc(arc):
    n, rows = len(arc), []
    for i, p in enumerate(arc):
        no    = n - i                                  # oldest essay is 01
        sub   = html.escape((p.get('subtitle') or '').strip())
        y, m, d = p['post_date'][:10].split('-')
        rows.append(
            '<li><a href="%s" target="_blank" rel="noopener">\n'
            '        <span><span class="ti">%s</span>%s</span>\n'
            '        <span class="meta"><span class="dept">%s</span>'
            '<span class="dt">%s.%s.%s</span></span>\n'
            '      </a></li>' % (
                html.escape(p['canonical_url']),
                html.escape(p['title'].strip()),
                '<span class="su">%s</span>' % sub if sub else '',
                html.escape(DEPT.get(p['slug'], 'Essay')), d, m, y[2:]))
    return '\n    '.join(rows)


def build_depts(arc):
    c = collections.Counter()
    for p in arc:
        for t in p.get('postTags', []):
            raw = t['name'].strip().lower()
            c[TAG_FIX.get(raw, raw.title())] += 1
    items = ['<a href="https://aguytalks.substack.com/archive" target="_blank" '
             'rel="noopener">%s<sup>%02d</sup></a>' % (k, v)
             for k, v in c.most_common() if v >= 2]
    return '\n    <span class="sep">/</span>\n    '.join(items)


# ---------------------------------------------------------------- photos

def build_cover():
    p = find_photo('cover')
    if p:
        print('  cover      %s' % os.path.basename(p))
        return ('<img src="%s" alt="SJ Singh, @aguytalks." fetchpriority="high" decoding="async">'
                % asset('cover.jpg', prep_image(p, 2000, 70)))
    print('  cover      (fallback - drop photos/cover.jpg to replace)')
    return ('<img src="%s" alt="Cover image." fetchpriority="high" decoding="async">'
            % asset('cover.jpg', prep_image(os.path.join(ASSETS, 'fallback-cover.jpg'), 1400, 62)))


def build_plate():
    p = find_photo('plate')
    if p:
        print('  plate      %s' % os.path.basename(p))
        return ('<img src="data:image/jpeg;base64,%s" alt="Detail from the essay.">'
                % prep_image(p, 1200, 66),
'')
    print('  plate      (fallback)')
    return ('<img src="data:image/jpeg;base64,%s" alt="Maison Margiela Tabi shoes '
            'on a concrete floor.">'
            % prep_image(os.path.join(ASSETS, 'fallback-plate.jpg'), 1200, 64),
'')


def build_portrait():
    p = find_photo('portrait')
    if p:
        print('  portrait   %s' % os.path.basename(p))
        return ('<img src="%s" alt="Portrait of SJ Singh." loading="lazy" decoding="async">'
                % asset('portrait.jpg', prep_image(p, 1300, 66)))
    print('  portrait   (none - drop photos/portrait.jpg to fill)')
    return '' 


def build_lookbook():
    """Returns (figures_html, count_label)."""
    looks = find_looks()
    if not looks:
        print('  lookbook   (none - drop photos/look-1.jpg, look-2.jpg, ...)')
        return '', '0 plates'
    print('  lookbook   %d image%s' % (len(looks), '' if len(looks) == 1 else 's'))
    caps = look_captions(len(looks))
    figs = []
    for i, path in enumerate(looks):
        data = prep_image(path, 1400, 62)
        if not data:
            continue
        cap = caps[i]
        figs.append(
            '<figure>\n'
            '      <img src="%s" alt="%s" loading="lazy" decoding="async">\n'
            '      <figcaption><span>%s</span><span>%02d / %02d</span></figcaption>\n'
            '    </figure>' % (asset('plate-%02d.jpg' % (i + 1), data),
                               html.escape(cap), html.escape(cap), i + 1, len(looks)))
    return '\n    '.join(figs), '%d plates' % len(figs)


# ---------------------------------------------------------------- main

def main():
    print('Building A Guy Talks...')
    arc = fetch_archive()
    print('  essays     %d from Substack' % len(arc))

    plate_img, plate_cap = build_plate()

    t = io.open(os.path.join(HERE, 'template.html'), encoding='utf-8').read()
    for w in ('400', '500', '600'):
        src = asset('poppins-%s.woff2' % w,
                    b64(os.path.join(ASSETS, 'poppins-%s.woff2' % w)), 'font/woff2')
        t = t.replace('__FONTSRC%s__' % w, src)
    look_html, look_count = build_lookbook()
    portrait = build_portrait()
    t = t.replace('__COVER_IMG__',      build_cover())
    t = t.replace('__PLATE_IMG__',      plate_img)
    t = t.replace('__PLATE_CAP__',      plate_cap)
    t = t.replace('__PORTRAIT__',       portrait)
    t = t.replace('__LOOKBOOK__',       look_html)
    t = t.replace('__TOC__',            build_toc(arc))

    left = [tok for tok in ('__COVER_IMG__', '__PLATE_IMG__', '__PORTRAIT__',
                            '__LOOKBOOK__', '__TOC__',
                            '__FONTSRC400__', '__FONTSRC500__', '__FONTSRC600__') if tok in t]
    if left:
        print('  ! unfilled placeholders: %s' % ', '.join(left), file=sys.stderr)

    out = os.path.join(DIST, 'index.html') if SPLIT else os.path.join(HERE, 'index.html')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    io.open(out, 'w', encoding='ascii', errors='xmlcharrefreplace').write(t)
    print('  written    %s  (%.2f MB)'
          % (os.path.relpath(out, HERE), os.path.getsize(out) / 1024 / 1024))
    if SPLIT:
        cname = os.path.join(DIST, 'CNAME')
        if LIVE:
            with open(cname, 'w') as f:
                f.write(DOMAIN + '\n')
            print('  CNAME      %s' % DOMAIN)
        elif os.path.exists(cname):
            os.remove(cname)
        with open(os.path.join(DIST, '.nojekyll'), 'w') as f:
            f.write('')
        tot = sum(os.path.getsize(os.path.join(r, f))
                  for r, _, fs in os.walk(DIST) for f in fs)
        print('  dist total %.2f MB (assets cache separately)' % (tot / 1024 / 1024))


if __name__ == '__main__':
    main()
