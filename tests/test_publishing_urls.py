import importlib.util
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def load_server(environment):
    clean_environment = {
        key: value for key, value in os.environ.items()
        if key not in {"GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "RSS_SITE_URL"}
    }
    clean_environment.update(environment)
    spec = importlib.util.spec_from_file_location("rss_server", ROOT / "server.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(os.environ, clean_environment, clear=True):
        spec.loader.exec_module(module)
    return module


class PublishingUrlsTest(unittest.TestCase):
    def check_generated_urls(self, environment, site_url, repository_url):
        server = load_server(environment)
        sources = server.load_journals()

        def fixture_source(source, cache):
            return {"link": source["homepage"], "description": "Fixture feed"}, [{
                "title": "Machine translation and interpreter education",
                "link": f"https://example.test/{source['slug']}",
                "doi": f"10.1234/{source['slug']}",
                "date": "2026-10-25T00:00:00+00:00",
                "abstract": "A study of machine translation and interpreter education.",
                "source_slug": source["slug"],
                "source_title": source["title"],
            }]

        with patch.object(server, "load_json", return_value={}), \
                patch.object(server, "load_journals", return_value=sources), \
                patch.object(server, "save_json"), \
                patch.object(server, "generate_source", side_effect=fixture_source):
            outputs = server.generate_all_feeds()
        server.validate_static_outputs(outputs, sources)

        for filename, content in outputs.items():
            with self.subTest(file=filename):
                self.assertNotIn("xionglingsong.github.io", content)
                self.assertNotIn("github.com/xionglingsong/", content)
                if filename.endswith(".xml") and filename not in {
                    f"{source['slug']}.xml" for source in sources
                }:
                    expected = site_url if filename == "feed.xml" else site_url + filename
                    self.assertEqual(ET.fromstring(content).findtext("channel/link"), expected)

        homepage = outputs["index.html"]
        self.assertIn(f'<code id="combined-url">{site_url}feed.xml</code>', homepage)
        self.assertIn(f"const baseUrl = {json.dumps(site_url)};", homepage)
        for path in ("edit/main/journals.json", "actions/workflows/publish-feed.yml", "settings/secrets/actions"):
            self.assertIn(f'href="{repository_url}/{path}"', homepage)
        self.assertIn(f"订阅入口：{site_url}", outputs["weekly/latest.md"])

        outlines = ET.fromstring(outputs["subscriptions.opml"]).findall(".//outline[@xmlUrl]")
        self.assertGreater(len(outlines), len(sources))
        for outline in outlines:
            self.assertEqual(outline.attrib["htmlUrl"], site_url)
            url = outline.attrib["xmlUrl"]
            self.assertTrue(url.startswith(site_url), url)
            self.assertIn(url[len(site_url):], outputs)

    def test_current_publication_urls(self):
        self.check_generated_urls(
            {}, "https://yileme.github.io/rss-translation-studies/",
            "https://github.com/yileme/rss-translation-studies",
        )

    def test_repository_rename_updates_every_generated_url(self):
        self.check_generated_urls(
            {"GITHUB_REPOSITORY": "next-owner/renamed-feeds"},
            "https://next-owner.github.io/renamed-feeds/",
            "https://github.com/next-owner/renamed-feeds",
        )

    def test_configured_pages_url(self):
        self.check_generated_urls(
            {"GITHUB_REPOSITORY": "next-owner/renamed-feeds", "RSS_SITE_URL": "https://feeds.example.test/library"},
            "https://feeds.example.test/library/",
            "https://github.com/next-owner/renamed-feeds",
        )

    def test_published_feed_fallback_uses_current_site_url(self):
        server = load_server({"RSS_SITE_URL": "https://feeds.example.test/library/"})
        source = {"slug": "fixture", "title": "Fixture journal"}
        with patch.object(server, "parse_source_feed", side_effect=RuntimeError("Source unavailable")), \
                patch.object(server, "fetch_text", return_value='<rss><channel><title>Fixture</title></channel></rss>') as fetch:
            feed, items = server.generate_source(source, {})
        self.assertEqual(items, [])
        self.assertIn("Source unavailable", feed["fallback_reason"])
        fetch.assert_called_once_with(
            "https://feeds.example.test/library/fixture.xml",
            accept="application/rss+xml, application/atom+xml, application/xml, text/xml",
            timeout=10, attempts=1,
        )


if __name__ == "__main__":
    unittest.main()
