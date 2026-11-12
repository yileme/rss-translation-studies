import copy
import json
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_publishing_urls import load_server


class MediaAccessibilityTest(unittest.TestCase):
    def setUp(self):
        self.server = load_server({})
        self.source = next(
            source for source in self.server.load_journals()
            if source["slug"] == "journal-deaf-studies-education"
        )

    def item(self, title, abstract="", identity="accessible", source=None):
        source = source or self.source
        return {
            "title": title, "abstract": abstract,
            "doi": f"10.1234/{identity}", "link": f"https://example.test/{identity}",
            "date": "2026-11-01T00:00:00+00:00",
            "source_slug": source["slug"], "source_title": source["title"],
        }

    def feed(self, source, items):
        return {"title": source["title"], "link": source["homepage"], "items": items}

    def test_audio_description_and_accessible_captions(self):
        titles = (
            "From policy to practice: Transforming audio description in China",
            "Audio-described museum visits for blind visitors",
            "Audiodescription and accessibility for low-vision audiences",
            "Descriptive video services and film reception",
            "Video descriptions for visually impaired viewers",
            "Closed captioning in online lectures",
            "Open captions for deaf and hard-of-hearing viewers",
            "Automatic captioning and access for DHH students",
            "Subtitles for the deaf and hard of hearing in education",
            "SDH in audiovisual media",
            "AD for blind film audiences",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(self.server.media_accessibility_related(self.item(title)))
                self.assertTrue(self.server.cross_disciplinary_related(self.item(title)))

    def test_biomedical_and_unrelated_disability_studies_are_excluded(self):
        titles = (
            "AD in Alzheimer's disease: Blind patients watching videos",
            "SDH: Succinate dehydrogenase in a double-blind video experiment",
            "Image captioning for blind video viewers",
            "Figure captions for deaf video learners",
            "AI-assisted wheelchair rehabilitation",
            "Deaf students' mathematics achievement",
            "Interpreting disability statistics",
            "Editorial: Audio description in inclusive education",
            "Review of Audio description and the blind audience",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertFalse(self.server.media_accessibility_related(self.item(title)))
                self.assertFalse(self.server.cross_disciplinary_related(self.item(title)))

    def test_abbreviations_require_accessibility_context(self):
        self.assertFalse(self.server.media_accessibility_related(self.item("An AD study")))
        self.assertFalse(self.server.media_accessibility_related(self.item("Preferences for SDH")))
        self.assertTrue(self.server.media_accessibility_related(self.item("AD for blind museum audiences")))
        self.assertTrue(self.server.media_accessibility_related(self.item("SDH for film audiences")))

    def test_accessible_media_keeps_audiovisual_and_accessibility_topics(self):
        for title in ("Audio description in museums", "SDH for film audiences"):
            with self.subTest(title=title):
                item = self.item(title)
                self.server.classify_item(item, ["cognition-process"])
                self.assertIn("audiovisual-translation", item["source_tags"])
                self.assertIn("disability-accessibility", item["source_tags"])

    def test_new_journals_have_explicit_scope_and_correct_crossref_issn(self):
        sources = self.server.load_journals()
        additions = [source for source in sources if source.get("discipline") == "disability-accessibility"]
        self.assertEqual(len(additions), 6)
        for source in additions:
            self.assertEqual(source["article_filter"], "translation-related")
            self.assertIn("disability-accessibility", source["tags"])
            self.assertTrue(source["indexing_evidence"].startswith("https://"))
        annals = next(source for source in additions if source["slug"] == "american-annals-deaf")
        self.assertEqual(annals["issn"], "1543-0375")
        self.assertEqual(annals["print_issn"], "0002-726X")

    def test_sdh_candidate_is_enriched_then_filtered(self):
        candidate = self.item("Preferences for SDH")
        self.assertTrue(self.server.related_research_candidate(candidate))
        for abstract, expected_count in (
            ("We examined preferences among deaf audiences viewing films.", 1),
            ("A study of succinate dehydrogenase enzymes.", 0),
        ):
            with self.subTest(abstract=abstract), patch.object(
                self.server, "parse_source_feed", return_value=self.feed(self.source, [copy.deepcopy(candidate)])
            ), patch.object(
                self.server, "enrich_item", side_effect=lambda item, cache: {**item, "abstract": abstract}
            ):
                _, items = self.server.generate_source(self.source, {})
                self.assertEqual(len(items), expected_count)

    def test_fallback_retains_only_related_accessibility_papers(self):
        related = self.item("Audio description for blind film audiences", identity="related")
        unrelated = self.item("Assistive wheelchairs and mobility", identity="unrelated")
        cache = {"_source_snapshots": {
            self.source["slug"]: {
                "feed": self.feed(self.source, [related, unrelated]), "fetched_at": time.time(),
            },
        }}
        with patch.object(self.server, "parse_source_feed", side_effect=RuntimeError("offline")), patch.object(
            self.server, "enrich_item", side_effect=lambda item, cache: item
        ):
            feed, items = self.server.generate_source(self.source, cache)
        self.assertTrue(feed["fallback_reason"])
        self.assertEqual([item["doi"] for item in items], [related["doi"]])

    def test_accessibility_feed_combines_new_and_preexisting_journals(self):
        old_source = next(
            source for source in self.server.load_journals()
            if source["slug"] == "computers-human-behavior"
        )
        caption = self.item("SDH for deaf film audiences", identity="sdh")
        unrelated = self.item("Wheelchair mobility and rehabilitation", identity="unrelated")
        description = self.item("Audio description and blind film viewers", identity="ad", source=old_source)
        def parsed(source):
            items = [caption, unrelated] if source["slug"] == self.source["slug"] else [description]
            return self.feed(source, copy.deepcopy(items))
        sources = [self.source, old_source]
        with patch.object(self.server, "load_journals", return_value=sources), patch.object(
            self.server, "parse_source_feed", side_effect=parsed
        ), patch.object(self.server, "enrich_item", side_effect=lambda item, cache: item), patch.object(
            self.server, "load_json", return_value={}
        ), patch.object(self.server, "save_json"):
            outputs = self.server.generate_all_feeds()
        self.server.validate_static_outputs(outputs, sources)
        root = ET.fromstring(outputs["topic-disability-accessibility.xml"])
        self.assertEqual(len(root.findall("channel/item")), 2)
        self.assertIn("topic-disability-accessibility.xml", outputs["subscriptions.opml"])
        self.assertIn("残障与视听无障碍", outputs["index.html"])
        self.assertFalse(json.loads(outputs["manifest.json"])["errors"])


if __name__ == "__main__":
    unittest.main()
