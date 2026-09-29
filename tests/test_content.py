import unittest

from content import clean_body_content, extract_body_content, split_dom_content


class ContentTests(unittest.TestCase):
    def test_extract_and_clean_body(self):
        html = "<html><body><nav>Navigation</nav><p>Useful content</p><!-- secret -->"
        html += "<script>alert('hidden')</script></body></html>"
        cleaned = clean_body_content(extract_body_content(html))
        self.assertEqual(cleaned, "Useful content")

    def test_chunking_preserves_text(self):
        chunks = split_dom_content("abcdefgh", 3)
        self.assertEqual(chunks, ["abc", "def", "gh"])
        self.assertEqual("".join(chunks), "abcdefgh")

    def test_invalid_chunk_size_rejected(self):
        with self.assertRaises(ValueError):
            split_dom_content("text", 0)


if __name__ == "__main__":
    unittest.main()
