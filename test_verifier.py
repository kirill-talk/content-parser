"""
Unit tests for the Content Verification Engine (verifier_core.py).
"""

import unittest
from verifier_core import (
    normalize_text,
    calculate_similarity,
    extract_social_embed_urls,
    parse_target_page,
    compare_article
)

class TestVerifierCore(unittest.TestCase):

    def test_normalize_text(self):
        html_input = "<p>Hello&nbsp;<strong>World!</strong></p>\n<div>Next&amp;Line</div>"
        cleaned = normalize_text(html_input)
        self.assertEqual(cleaned, "Hello World! Next&Line")

    def test_calculate_similarity(self):
        t1 = "De potanthurium is een prachtige bloem."
        t2 = "<p>De potanthurium is een prachtige bloem.</p>"
        self.assertEqual(calculate_similarity(t1, t2), 1.0)

        t3 = "De potanthurium is een fantastische plant."
        sim = calculate_similarity(t1, t3)
        self.assertTrue(0.5 < sim < 1.0)

    def test_extract_social_embed_urls(self):
        sample_html = """
        <div class="box" data-url="https://www.instagram.com/reel/DNFZOOPI-HI/?utm_source=ig_web_copy_link"></div>
        <p>Bekijk ook deze reel: https://www.instagram.com/p/C-xyz123/</p>
        <p>TikTok video: https://www.tiktok.com/@anthuriuminfo/video/7602241284266265889</p>
        """
        embeds = extract_social_embed_urls(sample_html)
        self.assertIn("https://www.instagram.com/reel/DNFZOOPI-HI/", embeds["instagram"])
        self.assertIn("https://www.instagram.com/reel/C-xyz123/", embeds["instagram"])
        self.assertTrue(any("7602241284266265889" in u for u in embeds["tiktok"]))

    def test_parse_target_page(self):
        sample_target_html = """
        <!DOCTYPE html>
        <html>
        <body>
            <section id="custom-block-28055845">
                <h1 class="heading-2 dark">Test Titel Artikel</h1>
                <div class="text-3 dark"><p>Dit is de introductie tekst.</p></div>
            </section>
            <section id="custom-block-28056034">
                <div class="box" data-url="https://www.instagram.com/reel/DNFZOOPI-HI/"></div>
                <div class="text-3 dark"><p>Dit is de eerste alinea van het artikel.</p></div>
            </section>
            <section id="custom-block-28056038">
                <div class="text-3 dark"><p>Dit is het tweede tekstblok.</p></div>
            </section>
        </body>
        </html>
        """
        parsed = parse_target_page(sample_target_html, target_url="https://test13242.mach3blocks.io/nl/blog/test-artikel/")
        self.assertEqual(parsed["title"], "Test Titel Artikel")
        self.assertIn("introductie", parsed["intro_text"])
        self.assertIn("eerste alinea", parsed["text_1"])
        self.assertIn("tweede tekstblok", parsed["text_2"])
        self.assertIn("https://www.instagram.com/reel/DNFZOOPI-HI/", parsed["boxes_with_data_url"])

    def test_compare_article_match(self):
        source = {
            "title": {"rendered": "Test Titel Artikel"},
            "slug": "test-titel-artikel",
            "link": "https://anthuriuminfo.com/blog/test-titel-artikel/",
            "content": {
                "rendered": """
                <p>Dit is de introductie tekst.</p>
                <!--more-->
                <p>https://www.instagram.com/reel/DNFZOOPI-HI/</p>
                <p>Dit is de eerste alinea van het artikel.</p>
                """
            }
        }
        target = {
            "url": "https://test13242.mach3blocks.io/nl/blog/test-titel-artikel~abc12345/",
            "title": "Test Titel Artikel",
            "intro_text": "<p>Dit is de introductie tekst.</p>",
            "text_1": "<p>Dit is de eerste alinea van het artikel.</p>",
            "text_2": "",
            "boxes_with_data_url": ["https://www.instagram.com/reel/DNFZOOPI-HI/"],
            "embed_urls": {"instagram": ["https://www.instagram.com/reel/DNFZOOPI-HI/"], "tiktok": []}
        }
        res = compare_article(source, target)
        self.assertEqual(res["status"], "PASSED")
        self.assertEqual(res["embeds"]["status"], "MATCH")
        self.assertEqual(res["title"]["status"], "MATCH")

    def test_compare_article_missing_embed(self):
        source = {
            "title": {"rendered": "Test Titel Artikel"},
            "slug": "test-titel-artikel",
            "link": "https://anthuriuminfo.com/blog/test-titel-artikel/",
            "content": {
                "rendered": "<p>Intro</p><p>https://www.instagram.com/reel/MISSING123/</p><p>Content</p>"
            }
        }
        target = {
            "url": "https://test13242.mach3blocks.io/nl/blog/test-titel-artikel~abc12345/",
            "title": "Test Titel Artikel",
            "intro_text": "<p>Intro</p>",
            "text_1": "<p>Content</p>",
            "text_2": "",
            "boxes_with_data_url": [],
            "embed_urls": {"instagram": [], "tiktok": []}
        }
        res = compare_article(source, target)
        self.assertEqual(res["status"], "FAILED")
        self.assertEqual(res["embeds"]["status"], "MISSING")

if __name__ == "__main__":
    unittest.main()
