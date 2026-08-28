from __future__ import annotations

import unittest

from ai_news_agent.normalize import canonicalize_url, normalize_and_rank


class NormalizeTests(unittest.TestCase):
    def test_canonicalize_removes_tracking_and_fragment(self) -> None:
        value = canonicalize_url("https://www.Example.com/a/?utm_source=x&b=2#part")
        self.assertEqual(value, "https://example.com/a?b=2")

    def test_deduplicates_same_story_and_merges_evidence(self) -> None:
        seed = {
            "edition_date": "2026-08-28",
            "items": [
                {
                    "title": "团队发布 Alpha 模型",
                    "url": "https://example.com/alpha?utm_source=x",
                    "source_name": "official",
                    "source_tier": 1,
                    "is_primary_source": True,
                    "evidence_urls": ["https://example.com/alpha"],
                },
                {
                    "title": "团队发布 Alpha 模型！",
                    "url": "https://news.example.net/alpha",
                    "source_name": "index",
                    "source_tier": 3,
                    "discovery_urls": ["https://news.example.net/alpha"],
                    "evidence_urls": ["https://news.example.net/alpha"],
                },
            ],
        }
        result = normalize_and_rank(seed)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["source_tier"], 1)
        self.assertEqual(len(result[0]["evidence_urls"]), 2)


if __name__ == "__main__":
    unittest.main()
