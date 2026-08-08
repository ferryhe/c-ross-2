from pathlib import Path
from xml.etree import ElementTree


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = REPO_ROOT / "AI_Agent" / "frontend" / "public"
DIST_DIR = REPO_ROOT / "AI_Agent" / "frontend" / "dist"
SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"


def test_built_crawler_files_match_public_sources_byte_for_byte() -> None:
    for filename in ("robots.txt", "sitemap.xml"):
        public_path = PUBLIC_DIR / filename
        dist_path = DIST_DIR / filename

        assert dist_path.is_file()
        assert dist_path.read_bytes() == public_path.read_bytes()


def test_robots_declares_public_and_private_routes() -> None:
    robots_path = PUBLIC_DIR / "robots.txt"

    assert robots_path.is_file()
    rules = [
        line.strip()
        for line in robots_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert rules == [
        "User-agent: *",
        "Allow: /",
        "Disallow: /api/",
        "Disallow: /healthz",
        "Disallow: /docs",
        "Disallow: /redoc",
        "Disallow: /openapi.json",
        "Sitemap: https://cross.aiactuary.cn/sitemap.xml",
    ]
    assert not any(rule.lower().startswith("allow: /api") for rule in rules)


def test_sitemap_contains_only_the_canonical_root() -> None:
    sitemap_path = PUBLIC_DIR / "sitemap.xml"

    assert sitemap_path.is_file()
    root = ElementTree.parse(sitemap_path).getroot()

    assert root.tag == f"{{{SITEMAP_NAMESPACE}}}urlset"
    url_elements = list(root)
    assert len(url_elements) == 1
    assert url_elements[0].tag == f"{{{SITEMAP_NAMESPACE}}}url"

    url_children = list(url_elements[0])
    assert [child.tag for child in url_children] == [f"{{{SITEMAP_NAMESPACE}}}loc"]
    assert url_children[0].text == "https://cross.aiactuary.cn/"
