# Translation Studies RSS

Enhanced RSS feeds for translation and interpreting studies journals. The generator reads official journal RSS feeds, enriches entries with public DOI metadata when needed, and publishes both a combined feed and per-journal feeds.

## Run Locally

```bash
python3 server.py
```

Then subscribe to this URL in NetNewsWire:

```text
http://127.0.0.1:8765/feed.xml
```

Per-journal feeds are also available locally, for example:

```text
http://127.0.0.1:8765/target.xml
http://127.0.0.1:8765/translation-studies.xml
```

Topic feeds are generated from each article's title and abstract, with journal tags used only as a fallback, for example:

```text
http://127.0.0.1:8765/topic-interpreting.xml
http://127.0.0.1:8765/topic-digital-ai-translation.xml
```

## Notes

- Journals are configured in `journals.json`.
- Metadata is fetched from Semantic Scholar, OpenAlex, and Crossref.
- Metadata is cached in `work/metadata-cache.json` for 30 days.
- Local generated feeds are cached in memory for 30 minutes.
- Chinese translations are added with `deepseek-v4-flash` when `TRANSLATE_TO_ZH=1` and `DEEPSEEK_API_KEY` are set.
- Static publishing validates the generated site before deployment. If any configured journal is missing or any source fails, the build stops instead of publishing a partial feed.

## Generate a Static Feed

```bash
python3 server.py --once public/feed.xml
```

This writes `public/feed.xml`, `public/index.html`, `public/papers.html`, and one XML file per journal. It also writes `new.xml`, rolling newly discovered-item feeds for the past 7 and 30 days (`new-7d.xml`, `new-30d.xml`), per-topic newly discovered-item feeds, and curated keyword-alert feeds (`alert-*.xml`). The paper index supports client-side keyword, topic, article-type, publication-window filtering, sorting, shareable filter links, citation-information copying, and related-paper recommendations across all currently collected items.

The static build also writes a rendered weekly digest at `public/weekly/latest.html`, plus Markdown drafts at `public/weekly/latest.md` and `public/weekly/YYYY-MM-DD.md`.

The generator records each article's first observed appearance in its existing cache. The first run establishes a baseline; later runs surface newly observed papers on the homepage.

The static build checks that every journal in `journals.json` produced a feed. A failed source, missing per-journal XML file, missing topic feed, missing weekly page, missing weekly Markdown draft, or journal-count mismatch will raise an error.

To include Chinese translations locally:

```bash
TRANSLATE_TO_ZH=1 DEEPSEEK_API_KEY=your_api_key python3 server.py --once public/feed.xml
```

When run on this Mac, the dated weekly digest is also copied to the Obsidian publishing folder if it exists:

```text
/Users/lingsongxiong/Nutstore Files/Obsidian/claudesidian-0.13.1/01_Projects/译了么/公众号/RSS
```

Override the target with `RSS_OBSIDIAN_WEEKLY_DIR=/path/to/folder`.

## Host on GitHub Pages

1. Create a GitHub repository and push these files to the `main` branch.
2. In the repository, open `Settings > Pages`.
3. Set `Build and deployment > Source` to `GitHub Actions`.
4. Open the `Actions` tab and run `Publish RSS feed` once, or push to `main`.
5. Subscribe to:

```text
https://YOUR-GITHUB-USERNAME.github.io/YOUR-REPOSITORY/feed.xml
```

The included workflow refreshes the feed every 6 hours and can also be run manually. It obtains the published site URL from GitHub Pages and the repository identity from `GITHUB_REPOSITORY`, so generated links follow username, repository, or custom-domain changes automatically.

For local builds, the default published site is `https://yileme.github.io/rss-translation-studies/`. Set `RSS_SITE_URL` to override the published site URL and `GITHUB_REPOSITORY=owner/repository` to override repository links. After changing a GitHub username, existing readers must update their subscription URLs because the old GitHub Pages domain does not redirect.

For this repository, the combined feed is:

```text
https://yileme.github.io/rss-translation-studies/feed.xml
```

## Included Journals

- Translation Studies
- Perspectives
- The Translator
- The Interpreter and Translator Trainer
- Asia Pacific Translation and Intercultural Studies
- Translation Review
- Target
- Interpreting
- Translation and Interpreting Studies
- Translation & Interpreting
- Translation Spaces
- Babel
- FORUM
- Translation in Society
- Translation, Cognition & Behavior
- Translation and Translanguaging in Multilingual Contexts
- Digital Translation
- InContext
- Terminology
- Meta
- MonTi
- Journal of Audiovisual Translation
- The Journal of Specialised Translation
- Interpreting and Society

## Cross-disciplinary SSCI Sources

The existing 24 translation-studies journals are unchanged. An additional 13 journals are monitored at article level, not subscribed wholesale:

- Cognitive neuroscience: Language, Cognition and Neuroscience; Journal of Neurolinguistics; Cortex.
- Psycholinguistics: Bilingualism: Language and Cognition; Applied Psycholinguistics; Journal of Memory and Language.
- Education and language learning: System; Language Learning; Computer Assisted Language Learning; ReCALL; Computers & Education; Language Learning & Technology.
- Human-computer interaction and behavior: Computers in Human Behavior (`computers-human-behavior.xml`).

Each added source uses `article_filter: "translation-related"` and a public `indexing_evidence` URL in `journals.json`. The original twelve cross-disciplinary sources also carry a `discipline` tag; Computers in Human Behavior uses the existing cognition, digital/AI and education topics rather than being mislabeled as a psycholinguistics journal. Public publisher/library indexing evidence was consulted on 2026-11-12; some evidence predates that date. This is a curated starting set, not an exhaustive SSCI list or a live Clarivate entitlement check. Index membership should be periodically rechecked against the Master Journal List.

For these sources, Crossref is scanned over a rolling 730-day publication window with cursor pagination (`lookback_days`, default 730; `search_rows`, default 100; `max_search_pages`, default 100). Only the metadata fields used by this project are requested; reference lists and other large unused fields are omitted. Requests use compressed responses when curl is available, a per-attempt wall-clock limit (`request_timeout`, default 20 seconds) and bounded retries (`request_attempts`, default 2). Truncated HTTP reads and malformed JSON are retried. Records are deduplicated by DOI/URL. Failed or incomplete API responses raise an error instead of masquerading as an empty successful feed. A healthy source with no related papers legitimately produces an empty feed.

Titles and available abstracts are screened for translation, interpreting, subtitling, dubbing, audio description and captioned-video research. Ambiguous translation/interpreter terms require a language context; protein translation, knowledge translation and image/figure captions are excluded. Missing abstracts are enriched when a title contains a potential translation/interpreting/caption keyword, then the final relevance filter is reapplied. Filtering occurs before the output limit (24 matching papers per added journal) and before Chinese translation, including when a cached or published fallback is used.

This rule-based approach prioritizes precision: it can miss papers whose titles contain no relevant keywords and whose abstracts are unavailable, and it does not search full texts. Intralingual captioned-video learning is intentionally included. Research papers and scholarly reviews remain eligible; the existing article-type feeds can narrow the result further.

Relevant papers enter the existing combined, topic, discovery and weekly feeds automatically. Three additional feeds preserve the source discipline even when article-level topic classification chooses other topics:

- `topic-cognitive-neuroscience.xml`
- `topic-psycholinguistics.xml`
- `topic-education-research.xml`

Changes to local files do not publish the site; publication still requires the normal GitHub Actions deployment.

## Classification Feeds

The project also publishes classification RSS feeds. Topic feeds are generated at article level from titles and abstracts, so different articles from the same journal can appear in different topic feeds.

- 综合翻译学: `topic-general-translation-studies.xml`
- 口译研究: `topic-interpreting.xml`
- 译者教育: `topic-translator-education.xml`
- 社会文化: `topic-society-culture.xml`
- 认知过程: `topic-cognition-process.xml`
- 数字与 AI 翻译: `topic-digital-ai-translation.xml`
- 视听翻译: `topic-audiovisual-translation.xml`
- 术语与专门用途翻译: `topic-terminology-specialized-translation.xml`
- 认知神经科学交叉研究: `topic-cognitive-neuroscience.xml`
- 心理语言学交叉研究: `topic-psycholinguistics.xml`
- 教育学交叉研究: `topic-education-research.xml`

Type feeds are generated from article titles and public metadata:

- Article: `type-article.xml`
- Review: `type-review.xml`
- Book Review: `type-book-review.xml`

## Weekly Digest

The site publishes a rendered weekly digest for readers and Markdown drafts for newsletters, WeChat posts, group updates, or Obsidian.

- Latest rendered digest: `weekly/latest.html`
- Latest Markdown draft: `weekly/latest.md`
- Dated rendered digest: `weekly/YYYY-MM-DD.html`
- Dated Markdown draft: `weekly/YYYY-MM-DD.md`

The digest uses items from the most recent 7 days. If no items fall within that window, it falls back to the latest 20 items so the generated article is still useful.

Taylor & Francis, John Benjamins, and JAT entries use Crossref on GitHub Pages because some publisher RSS endpoints may reject GitHub-hosted requests. Taylor & Francis items also try the publisher TDM XML link and a rendered-reader fallback when Crossref/OpenAlex/Semantic Scholar do not expose abstracts. SAGE and OJS feeds are enriched through DOI or article-page metadata when their RSS entries omit fields such as abstracts, DOIs, or pages. Some reviews or editorial material may not have a public abstract in any metadata source.

To publish Chinese translations on GitHub Pages, add a `DEEPSEEK_API_KEY` repository secret. The workflow already enables `TRANSLATE_TO_ZH`. To improve Taylor & Francis rendered-reader reliability or rate limits, optionally add `JINA_READER_API_KEY`.

## Maintenance Checklist

Use this checklist whenever adding or repairing a journal.

1. Add or update the journal in `journals.json`.
   - Include `slug`, `title`, `publisher`, `homepage`, and either `source_feed` or Crossref fields.
   - Add at least one `tags` value so the journal appears in the relevant topic feeds.
   - Prefer a stable official RSS feed when it works on GitHub Actions.
   - Use `source_type: "crossref"` when publisher RSS blocks GitHub-hosted requests or omits too much metadata.

2. Verify source quality locally.
   - Run `python3 server.py --once public/feed.xml`.
   - Open `public/manifest.json` and confirm `journal_count` equals the number of entries in `journals.json`.
   - Check `errors` is an empty list.
   - Review `weak_abstract_count` and the per-journal `weak_abstracts` values.
   - Review the `topics` and `types` sections and confirm each expected classification feed is present.
   - Open `public/weekly/latest.html` and confirm the weekly digest renders cleanly.
   - Open `public/weekly/latest.md` and confirm the Markdown draft has sensible grouping and links.

3. Check the public homepage.
   - Open `public/index.html`.
   - Confirm the journal list is complete.
   - Confirm each row shows source type, topic tags, current build status, item count, Chinese count, and abstract status.
   - Confirm the topic subscription cards show sensible journal and item counts.
   - Test the combined RSS button and at least one per-journal RSS link.

4. Update public documentation.
   - Keep the "Included Journals" list in this README in sync with `journals.json`.
   - Mention special source decisions, such as Crossref fallbacks or journals without official RSS.
   - If the change affects users, add a short update note for WeChat, the website, or the project announcement.

5. Publish safely.
   - Commit the code and config changes together.
   - Push to `main`.
   - Check the `Publish RSS feed` GitHub Actions run.
   - After deployment, open the live `manifest.json` and confirm the expected journal count.

## URL Regression Checks

```bash
python3 -m unittest discover -s tests -v
```

These checks generate all feeds, the homepage, OPML, and weekly digest without network requests, and cover repository renames, custom site URLs, and the published-feed fallback.
