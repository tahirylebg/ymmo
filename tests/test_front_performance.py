"""Front-end delivery: HTTP caching, compression, SEO metadata, the hero light and the brand
arcade."""

import json
import re

import pytest

from app.web.arcade import VIEW_H, VIEW_W, arcade_paths
from app.web.templating import templates

GZIP = {"Accept-Encoding": "gzip"}


def test_html_pages_are_compressed_and_revalidated(client, world):
    response = client.get("/", headers=GZIP)
    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.headers["cache-control"] == "no-cache"


def test_versioned_assets_are_immutable_and_compressed(client, world):
    html = client.get("/").text
    css = re.search(r'href="[^"]*(/static/css/main\.css\?v=\w+)"', html).group(1)
    response = client.get(css, headers=GZIP)
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["content-encoding"] == "gzip"

    # Without the version the same file is only cached for a day (then revalidated).
    plain = client.get("/static/css/main.css")
    assert plain.headers["cache-control"] == "public, max-age=86400"


def test_fonts_are_immutable_and_not_gzipped(client):
    response = client.get("/static/fonts/newsreader-latin-opsz-wght200-400.woff2", headers=GZIP)
    assert response.status_code == 200
    assert response.headers["content-type"] == "font/woff2"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "content-encoding" not in response.headers


def test_home_hero_keeps_poster_fallback_and_points_to_versioned_light_module(client, world):
    html = client.get("/").text
    version = templates.env.globals["ASSET_VERSION"]
    hero = re.search(r'<section class="hero"[^>]*>', html).group(0)
    src = re.search(r'data-light-src="[^"]*(/static/js/hero-light\.js\?v=\w+)"', hero).group(1)
    assert src.endswith(f"?v={version}")
    # The poster stays in the markup: it is what users see without JS or WebGL. One framing per
    # shape of screen, each in AVIF and WebP.
    assert 'class="hero-poster"' in html
    # The sell band's still beam ships the same way.
    for name in ("light-1920", "light-1200", "light-960", "beam-1920", "beam-900"):
        for ext in ("avif", "webp"):
            assert f"/static/img/hero/{name}.{ext}?v={version}" in html
            assert client.get(f"/static/img/hero/{name}.{ext}?v={version}").status_code == 200

    module = client.get(src)
    assert module.status_code == 200
    assert "javascript" in module.headers["content-type"]
    assert module.headers["cache-control"].endswith("immutable")
    # One small module, no library: it never imports anything.
    assert not re.search(r"^\s*import\b(?!\s*\()", module.text, re.M)


def test_other_pages_do_not_load_the_light_module(client, world):
    assert "hero-light" not in client.get("/biens").text


@pytest.mark.parametrize("count", [1, 2, 3, 5, 9])
def test_arcade_paths_fit_the_viewbox(count):
    paths = arcade_paths(count)
    assert set(paths) == {"main", "reveal", "voussoirs", "shadow"}
    numbers = [float(n) for d in paths.values() for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
    xs, ys = numbers[0::2], numbers[1::2]
    assert min(xs) >= -1 and max(xs) <= VIEW_W + 1
    assert min(ys) >= -1 and max(ys) <= VIEW_H + 1
    # One opening outline, extrados and back-edge arch per bay.
    assert paths["main"].count("M") >= 2 * count


def test_pages_have_their_own_description_and_canonical(client, world):
    descriptions = set()
    for url in ("/", "/biens", "/connexion", "/inscription", "/estimer"):
        html = client.get(url).text
        descriptions.add(re.search(r'<meta name="description" content="([^"]+)"', html).group(1))
        canonical = re.search(r'<link rel="canonical" href="([^"]+)"', html).group(1)
        assert canonical.endswith(url) and "?" not in canonical
    assert len(descriptions) == 5


def test_listing_page_has_open_graph_and_real_estate_structured_data(client, world):
    prop = world["flat"]
    html = client.get(f"/biens/{prop.id}?from=search").text
    assert f'<link rel="canonical" href="http://testserver/biens/{prop.id}">' in html
    assert re.search(r'<meta property="og:title" content="[^"]+">', html)
    assert re.search(r'<meta property="og:image" content="http://testserver/[^"]+">', html)

    raw = re.search(r'<script type="application/ld\+json">(.+?)</script>', html, re.S).group(1)
    data = json.loads(raw)
    assert data["@type"] == "RealEstateListing"
    assert data["name"] == prop.title
    assert data["offers"]["price"] == float(prop.price)
    assert data["offers"]["priceCurrency"] == "EUR"
    assert data["about"]["address"]["addressLocality"] == prop.city.name
    assert data["image"]
