import json
import unittest
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_publishing_urls import load_server


class CrossDisciplinaryTest(unittest.TestCase):
    def setUp(self):
        self.server = load_server({})
        self.source = next(
            source for source in self.server.load_journals()
            if source["slug"] == "bilingualism-language-cognition"
        )

    def item(self, title, abstract="", identity="related"):
        return {
            "title": title, "abstract": abstract,
            "doi": f"10.1234/{identity}", "link": f"https://example.test/{identity}",
            "date": "2026-11-01T00:00:00+00:00",
            "source_slug": self.source["slug"], "source_title": self.source["title"],
        }

    def test_relevant_papers(self):
        examples = [
            ("Neural mechanisms of simultaneous interpreting", ""),
            ("Working memory in consecutive interpreters", ""),
            ("Translation priming in bilingual word recognition", ""),
            ("The production of translation equivalents", ""),
            ("Processing during sight-translation", ""),
            ("Training professional translators", ""),
            ("Audiovisual translation and accessibility", ""),
            ("Learning vocabulary with subtitles", ""),
            ("Dubbing and second-language learning", ""),
            ("The reception of audio descriptions", ""),
            ("L2 listening with captioned videos", ""),
            ("Closed captions for deaf video viewers", ""),
            ("Cross-language translation tasks", ""),
            ("Neural control in bilinguals", "Participants translated words between languages."),
            ("An ERP investigation", "We studied sign-language interpreters."),
        ]
        for title, abstract in examples:
            with self.subTest(title=title):
                self.assertTrue(self.server.translation_related(self.item(title, abstract)))

    def test_unrelated_papers(self):
        examples = [
            ("Interpreting brain imaging results", "Language networks were measured."),
            ("Simultaneous processing in bilinguals", "A language comprehension study."),
            ("Consecutive learning sessions", "Students studied a second language."),
            ("Protein translation in neurons", "Language processing and gene expression."),
            ("Knowledge translation in education", "Language teachers translate research into practice."),
            ("Translating evidence into practice", "Language instruction and educational policy."),
            ("Image captioning for educational videos", "A computer vision benchmark."),
            ("Figure captions and video instruction", ""),
            ("The Python interpreter", "Computer programming language education."),
            ("Bilingual vocabulary acquisition", "Cognitive control in language learning."),
            ("Editorial: simultaneous interpreting", ""),
            ("Correction to: translation priming", ""),
            ("Book review: audiovisual translation", ""),
            ("Special issue on translation equivalents in bilingual memory", ""),
            ("Psychotic subtitles: A case of transient ticker-tape synesthesia", ""),
            ("Review of Technology in second language writing: Advances in translation", ""),
            ("ChatGPT in foreign language lesson plan creation", "Our results offer immediate translational implications for language teachers."),
            ("Foreign language speaking anxiety online", "Technology can be supportive, for example online translation tools and dictionaries."),
            ("Automated written corrective feedback", "ChatGPT flags language errors including word choice, direct translation, and sentence structure."),
        ]
        for title, abstract in examples:
            with self.subTest(title=title):
                self.assertFalse(self.server.translation_related(self.item(title, abstract)))

    def test_audiovisual_variants_keep_existing_topic_membership(self):
        for title in ("Learning with subtitles", "Learning with captions", "Captioned video learning", "Captioning in L2 listening"):
            with self.subTest(title=title):
                item = self.item(title)
                self.server.classify_item(item, self.source["tags"])
                self.assertIn("audiovisual-translation", item["source_tags"])

    def test_crossref_scans_window_not_output_limit(self):
        with patch.object(self.server, "api_json", return_value={"message": {"items": [], "total-results": 0}}) as fetch:
            self.server.parse_crossref_source(self.source)
        params = parse_qs(urlparse(fetch.call_args.args[0]).query)
        self.assertEqual(params["rows"], ["100"])
        self.assertIn("abstract", params["select"][0].split(","))
        self.assertIn("published", params["select"][0].split(","))
        self.assertIn("issued", params["select"][0].split(","))
        self.assertNotIn("reference", params["select"][0].split(","))
        self.assertEqual(params["cursor"], ["*"])
        self.assertEqual(params["sort"], ["indexed"])
        self.assertIn("from-pub-date:", params["filter"][0])
        self.assertEqual(fetch.call_args.kwargs["timeout"], 20)
        self.assertEqual(fetch.call_args.kwargs["attempts"], 2)
        self.assertNotIn("use_curl", fetch.call_args.kwargs)

    def test_selected_publication_dates_precede_registration_date(self):
        for publication_field in ("published", "issued", "published-online", "published-print"):
            with self.subTest(publication_field=publication_field):
                message = {
                    publication_field: {"date-parts": [[2026, 7, 16]]},
                    "created": {"date-parts": [[2026, 10, 25]]},
                }
                self.assertEqual(self.server.crossref_date(message), "2026-07-16T00:00:00+00:00")

    def test_cursor_pagination_and_deduplication(self):
        source = {**self.source, "search_rows": 2}
        first = {"DOI": "10.1234/ONE", "title": ["First"]}
        duplicate = {"DOI": "10.1234/one", "title": ["Duplicate"]}
        second = {"DOI": "10.1234/two", "title": ["Second"]}
        third = {"DOI": "10.1234/three", "title": ["Third"]}
        responses = [
            {"message": {"items": [first, second], "total-results": 3, "next-cursor": "page-two"}},
            {"message": {"items": [duplicate, third], "total-results": 3}},
        ]
        with patch.object(self.server, "api_json", side_effect=responses) as fetch:
            works = self.server.crossref_source_works(source)
        self.assertEqual(len(works), 3)
        self.assertEqual(parse_qs(urlparse(fetch.call_args.args[0]).query)["cursor"], ["page-two"])

    def test_failed_api_is_not_reported_as_empty(self):
        for response in ({}, {"message": {}}, {"message": {"items": None}}, {"message": {"items": []}}):
            with self.subTest(response=response), patch.object(self.server, "api_json", return_value=response):
                with self.assertRaises(RuntimeError):
                    self.server.parse_crossref_source(self.source)

    def test_missing_cursor_and_scan_limit_fail_closed(self):
        for response in (
            {"message": {"items": [], "total-results": 2}},
            {"message": {"items": [{"DOI": "10.1234/one"}], "total-results": 2}},
            {"message": {"items": [{"DOI": "10.1234/one"}], "total-results": 2, "next-cursor": "next"}},
        ):
            with self.subTest(response=response), patch.object(self.server, "api_json", return_value=response):
                with self.assertRaises(RuntimeError):
                    self.server.crossref_source_works({**self.source, "max_search_pages": 1})

    def test_existing_journal_keeps_latest_items_behavior(self):
        source = next(source for source in self.server.load_journals() if source["slug"] == "target")
        with patch.object(self.server, "api_json", return_value={"message": {"items": []}}) as fetch:
            self.server.parse_crossref_source(source)
        params = parse_qs(urlparse(fetch.call_args.args[0]).query)
        self.assertEqual(params["rows"], [str(self.server.MAX_ITEMS_PER_SOURCE)])
        self.assertNotIn("cursor", params)
        self.assertEqual(params["sort"], ["published"])
        self.assertEqual(params["filter"], ["type:journal-article"])

    def test_crossref_request_can_bypass_curl(self):
        with patch.object(self.server, "fetch_text", return_value='{"message": {"items": []}}') as fetch_text, \
                patch.object(self.server.subprocess, "run") as run:
            self.server.api_json("https://api.crossref.org/example", timeout=30, use_curl=False)
        run.assert_not_called()
        self.assertFalse(fetch_text.call_args.kwargs["use_curl"])
        self.assertEqual(fetch_text.call_args.kwargs["timeout"], 30)

    def test_incomplete_http_download_is_retried(self):
        with patch.object(self.server.urllib.request, "urlopen") as urlopen, \
                patch.object(self.server.time, "sleep"):
            response = urlopen.return_value.__enter__.return_value
            response.read.side_effect = [self.server.http.client.IncompleteRead(b"partial"), b"complete"]
            response.headers.get_content_charset.return_value = "utf-8"
            result = self.server.fetch_text("https://example.test/feed", attempts=2, use_curl=False)
        self.assertEqual(result, "complete")
        self.assertEqual(urlopen.call_count, 2)

    def test_json_curl_retries_are_bounded_and_compressed(self):
        success = self.server.subprocess.CompletedProcess([], 0, stdout='{"message": {"items": []}}')
        failures = [
            self.server.subprocess.CalledProcessError(18, "curl"),
            self.server.subprocess.TimeoutExpired("curl", 20),
            self.server.subprocess.CompletedProcess([], 0, stdout='{"message":'),
        ]
        for failure in failures:
            with self.subTest(failure=failure), \
                    patch.object(self.server.shutil, "which", return_value="/usr/bin/curl"), \
                    patch.object(self.server.subprocess, "run", side_effect=[failure, success]) as run, \
                    patch.object(self.server.time, "sleep"):
                result = self.server.api_json("https://example.test/api", timeout=20, attempts=2)
            self.assertEqual(result, {"message": {"items": []}})
            self.assertEqual(run.call_count, 2)
            self.assertEqual(run.call_args.kwargs["timeout"], 22)
            self.assertIn("--compressed", run.call_args.args[0])
            self.assertIn("--max-time", run.call_args.args[0])

    def test_json_retry_exhaustion_is_not_silent_success(self):
        with patch.object(self.server.shutil, "which", return_value="/usr/bin/curl"), \
                patch.object(self.server.subprocess, "run", side_effect=self.server.subprocess.TimeoutExpired("curl", 20)) as run, \
                patch.object(self.server.time, "sleep"):
            result = self.server.api_json("https://example.test/api", timeout=20, attempts=2)
        self.assertEqual(result, {})
        self.assertEqual(run.call_count, 2)

    def test_json_incomplete_read_without_curl_is_retried(self):
        with patch.object(self.server, "fetch_text", side_effect=[
            self.server.http.client.IncompleteRead(b"partial"), '{"message": {"items": []}}',
        ]) as fetch, patch.object(self.server.time, "sleep"):
            result = self.server.api_json("https://example.test/api", use_curl=False, attempts=2)
        self.assertEqual(result, {"message": {"items": []}})
        self.assertEqual(fetch.call_count, 2)

    def test_matching_papers_are_sorted_by_publication_before_limit(self):
        source = {**self.source, "max_items": 1}
        older = {**self.item("Machine translation for vocabulary", identity="older"), "date": "2025-01-01T00:00:00Z"}
        newer = {**self.item("Subtitles and vocabulary learning", identity="newer"), "date": "2026-06-01T00:00:00Z"}
        feed = {"title": "System", "link": self.source["homepage"], "items": [older, newer]}
        with patch.object(self.server, "parse_source_feed", return_value=feed), \
                patch.object(self.server, "enrich_item", side_effect=lambda item, cache: item):
            _, items = self.server.generate_source(source, {})
        self.assertEqual(items, [newer])

    def test_filter_precedes_limit_and_translation(self):
        source = {**self.source, "max_items": 1}
        unrelated = [self.item("Bilingual memory", identity=f"unrelated-{number}") for number in range(30)]
        related = self.item("Simultaneous interpreting", identity="match")
        feed = {"items": unrelated + [related]}
        with patch.object(self.server, "parse_source_feed", return_value=feed), \
                patch.object(self.server, "enrich_item", side_effect=lambda item, cache: item), \
                patch.object(self.server, "TRANSLATE_TO_ZH", True), \
                patch.object(self.server, "DEEPSEEK_API_KEY", "test-placeholder"), \
                patch.object(self.server, "translate_item", side_effect=lambda item, cache: item) as translate:
            _, items = self.server.generate_source(source, {})
        self.assertEqual([item["doi"] for item in items], [related["doi"]])
        translate.assert_called_once()

    def test_missing_abstract_candidate_is_enriched_then_filtered(self):
        candidate = self.item("Translation in the bilingual brain")
        irrelevant = self.item("Interpreting neural signals", identity="irrelevant")
        def enrich(item, cache):
            return {**item, "abstract": "Bilingual language translation tasks." if item is candidate else "Neural signal analysis."}
        with patch.object(self.server, "parse_source_feed", return_value={"items": [candidate, irrelevant]}), \
                patch.object(self.server, "enrich_item", side_effect=enrich) as enrichment, \
                patch.object(self.server, "TRANSLATE_TO_ZH", False):
            _, items = self.server.generate_source(self.source, {})
        self.assertEqual(len(items), 1)
        self.assertEqual(enrichment.call_count, 2)

    def test_cached_fallback_is_filtered(self):
        cache = {"_source_snapshots": {self.source["slug"]: {"feed": {
            "items": [self.item("Bilingual memory"), self.item("Simultaneous interpreting", identity="match")],
        }}}}
        with patch.object(self.server, "parse_source_feed", side_effect=RuntimeError("offline")), \
                patch.object(self.server, "enrich_item", side_effect=lambda item, cache: item), \
                patch.object(self.server, "TRANSLATE_TO_ZH", False):
            feed, items = self.server.generate_source(self.source, cache)
        self.assertIn("offline", feed["fallback_reason"])
        self.assertEqual([item["doi"] for item in items], ["10.1234/match"])

    def test_empty_related_feed_is_valid(self):
        with patch.object(self.server, "parse_source_feed", return_value={"items": [self.item("Bilingual memory")]}):
            _, items = self.server.generate_source(self.source, {})
        self.assertEqual(items, [])

    def test_configuration_and_discipline_feeds(self):
        sources = self.server.load_journals()
        filtered = [source for source in sources if source.get("article_filter")]
        self.assertEqual(len(sources), 43)
        self.assertEqual(len(filtered), 19)
        self.assertEqual(len({source["slug"] for source in sources}), len(sources))
        for source in filtered:
            if source.get("discipline"):
                self.assertIn(source["discipline"], source["tags"])
            self.assertTrue(source["indexing_evidence"].startswith("http"))
        def fixture(source, cache):
            item = self.item("Simultaneous interpreting", identity=source["slug"])
            item.update(source_slug=source["slug"], source_title=source["title"])
            return {"link": source["homepage"], "description": "Fixture"}, [item]
        with patch.object(self.server, "generate_source", side_effect=fixture), \
                patch.object(self.server, "load_json", return_value={}), \
                patch.object(self.server, "load_journals", return_value=sources), \
                patch.object(self.server, "save_json"):
            outputs = self.server.generate_all_feeds()
        self.server.validate_static_outputs(outputs, sources)
        for discipline, expected_count in (("cognitive-neuroscience", 3), ("psycholinguistics", 3), ("education-research", 6), ("disability-accessibility", 6)):
            filename = f"topic-{discipline}.xml"
            self.assertEqual(len(ET.fromstring(outputs[filename]).findall("channel/item")), expected_count)
            self.assertIn(filename, outputs["subscriptions.opml"])
            self.assertIn(filename, outputs["index.html"])
        self.assertEqual(outputs["index.html"].count('<span class="tag-chip">翻译、语言协作与视听无障碍</span>'), 19)
        human_behavior_feed = ET.fromstring(outputs["computers-human-behavior.xml"])
        self.assertEqual(len(human_behavior_feed.findall("channel/item")), 1)
        human_behavior_source = next(source for source in filtered if source["slug"] == "computers-human-behavior")
        self.assertEqual(human_behavior_source["issn"], "0747-5632")
        self.assertNotIn("discipline", human_behavior_source)
        manifest = json.loads(outputs["manifest.json"])
        self.assertFalse(manifest["errors"])


if __name__ == "__main__":
    unittest.main()
