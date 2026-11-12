import copy
import json
import time
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_publishing_urls import load_server


class LanguageCollaborationTest(unittest.TestCase):
    def setUp(self):
        self.server = load_server({})
        self.source = next(
            source for source in self.server.load_journals()
            if source["slug"] == "computers-human-behavior"
        )

    def item(self, title, abstract="", identity="collaboration"):
        return {
            "title": title, "abstract": abstract,
            "doi": f"10.1234/{identity}", "link": f"https://example.test/{identity}",
            "date": "2026-11-01T00:00:00+00:00",
            "source_slug": self.source["slug"], "source_title": self.source["title"],
        }

    def feed(self, items):
        return {"title": self.source["title"], "link": self.source["homepage"], "items": items}

    def test_language_teaching_and_translation_collaboration(self):
        titles = (
            "ChatGPT feedback in EFL writing instruction",
            "AI-assisted second-language learning and learner engagement",
            "Conversational agents for foreign-language speaking practice",
            "Automated corrective feedback for ESL students",
            "Robot-assisted foreign language learning",
            "Social robots in English teaching",
            "Intelligent tutoring systems in language education",
            "Computer-assisted language learning and student agency",
            "Human-AI collaboration in translator training",
            "Professional translators' trust in machine translation",
            "AI-assisted interpreting: cognitive workload in consecutive interpreters",
        )
        for title in titles:
            with self.subTest(title=title):
                self.assertTrue(self.server.language_collaboration_related(self.item(title)))
                self.assertTrue(self.server.cross_disciplinary_related(self.item(title)))

    def test_general_human_ai_and_unassisted_learning_stay_excluded(self):
        examples = (
            ("Understanding trust and distrust contagion in Human-AI Teams", ""),
            ("User cognitive fit in human-AI interaction", ""),
            ("Human-AI trust in investment decisions", ""),
            ("AI-assisted professional business writing", ""),
            ("ChatGPT in higher education", "Student agency and general educational outcomes."),
            ("Foreign language learning through peer collaboration", "No technology is involved."),
            ("Large language models and language proficiency benchmarks", "An AI capability evaluation."),
            ("Protein translation with artificial intelligence", "Gene expression and neuronal language networks."),
            ("Editorial: ChatGPT for EFL writing", ""),
            ("Review of ChatGPT in language education", ""),
        )
        for title, abstract in examples:
            with self.subTest(title=title):
                self.assertFalse(self.server.language_collaboration_related(self.item(title, abstract)))
                self.assertFalse(self.server.cross_disciplinary_related(self.item(title, abstract)))

    def test_known_chb_language_writing_case(self):
        item = self.item(
            "Bridging or broadening Gaps? AI-Assisted professional writing among native and non-native English Writers"
        )
        self.assertFalse(self.server.translation_related(item))
        self.assertTrue(self.server.language_collaboration_related(item))

    def test_language_context_in_abstract_is_enough(self):
        item = self.item(
            "Supporting student agency through intelligent tutoring",
            "This study investigates EFL learners using an AI assistant for second-language writing.",
        )
        self.assertTrue(self.server.language_collaboration_related(item))

    def test_candidate_enrichment_is_bounded_by_relevant_title_cues(self):
        self.assertTrue(self.server.related_research_candidate(self.item("AI-assisted writing and student engagement")))
        self.assertTrue(self.server.related_research_candidate(self.item("Digital feedback for EFL learners")))
        self.assertFalse(self.server.related_research_candidate(self.item("Motivation in EFL classrooms")))
        self.assertFalse(self.server.related_research_candidate(self.item("Trust in human-AI teams")))

    def test_new_topic_does_not_mislabel_language_writing_as_translation(self):
        item = self.item("AI-assisted writing among non-native English writers")
        self.server.classify_item(item, self.source["tags"])
        self.assertIn("language-human-ai-collaboration", item["source_tags"])
        self.assertNotIn("translator-education", item["source_tags"])
        self.assertNotIn("digital-ai-translation", item["source_tags"])

    def test_actual_translation_can_belong_to_both_topic_families(self):
        item = self.item("Human-AI collaboration in translator training and machine translation")
        self.server.classify_item(item, self.source["tags"])
        self.assertIn("language-human-ai-collaboration", item["source_tags"])
        self.assertIn("digital-ai-translation", item["source_tags"])

    def test_filter_runs_before_output_limit(self):
        source = {**self.source, "max_items": 1}
        unrelated = self.item("Trust in human-AI teams", identity="unrelated")
        relevant = self.item("ChatGPT feedback for EFL writers", identity="relevant")
        with patch.object(self.server, "parse_source_feed", return_value=self.feed([unrelated, relevant])), patch.object(
            self.server, "enrich_item", side_effect=lambda item, cache: item
        ):
            _, items = self.server.generate_source(source, {})
        self.assertEqual([item["doi"] for item in items], [relevant["doi"]])

    def test_recovered_abstract_is_checked_before_acceptance(self):
        candidate = self.item("AI-assisted writing and student engagement")
        for abstract, expected_count in (
            ("We examined EFL students learning through ChatGPT writing feedback.", 1),
            ("We examined managers writing business reports with AI.", 0),
            ("", 0),
        ):
            with self.subTest(abstract=abstract), patch.object(
                self.server, "parse_source_feed", return_value=self.feed([copy.deepcopy(candidate)])
            ), patch.object(
                self.server, "enrich_item", side_effect=lambda item, cache: {**item, "abstract": abstract}
            ):
                _, items = self.server.generate_source(self.source, {})
                self.assertEqual(len(items), expected_count)

    def test_cached_fallback_uses_the_expanded_filter(self):
        relevant = self.item("AI-assisted L2 writing", identity="relevant")
        unrelated = self.item("Trust in human-AI teams", identity="unrelated")
        cache = {"_source_snapshots": {
            self.source["slug"]: {"feed": self.feed([unrelated, relevant]), "fetched_at": time.time()},
        }}
        with patch.object(self.server, "parse_source_feed", side_effect=RuntimeError("offline")), patch.object(
            self.server, "enrich_item", side_effect=lambda item, cache: item
        ):
            feed, items = self.server.generate_source(self.source, cache)
        self.assertTrue(feed["fallback_reason"])
        self.assertEqual([item["doi"] for item in items], [relevant["doi"]])

    def test_new_feed_is_generated_from_actual_source_pipeline(self):
        relevant = self.item("ChatGPT feedback in EFL writing", identity="relevant")
        unrelated = self.item("Trust in human-AI teams", identity="unrelated")
        with patch.object(self.server, "load_journals", return_value=[self.source]), patch.object(
            self.server, "parse_source_feed", return_value=self.feed([relevant, unrelated])
        ), patch.object(self.server, "enrich_item", side_effect=lambda item, cache: item), patch.object(
            self.server, "load_json", return_value={}
        ), patch.object(self.server, "save_json"):
            outputs = self.server.generate_all_feeds()
        root = ET.fromstring(outputs["topic-language-human-ai-collaboration.xml"])
        self.assertEqual(len(root.findall("channel/item")), 1)
        self.assertEqual(root.findtext("channel/item/title"), f"[{self.source['title']}] {relevant['title']}")
        self.assertIn("语言教学与翻译人机协作", outputs["index.html"])
        self.assertIn("topic-language-human-ai-collaboration.xml", outputs["subscriptions.opml"])
        manifest = json.loads(outputs["manifest.json"])
        self.assertEqual(manifest["errors"], [])


if __name__ == "__main__":
    unittest.main()
