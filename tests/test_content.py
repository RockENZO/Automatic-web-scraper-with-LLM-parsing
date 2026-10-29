import unittest

from content import clean_body_content, extract_body_content, split_dom_content


class ContentTests(unittest.TestCase):
    def test_extract_and_clean_body(self):
        html = "<html><body><nav>Navigation</nav><p>Useful content</p><!-- secret -->"
        html += "<script>alert('hidden')</script></body></html>"
        cleaned = clean_body_content(extract_body_content(html))
        self.assertEqual(cleaned, "Useful content")

    def test_explicitly_hidden_content_never_reaches_free_text_input(self):
        for hidden in ['hidden', 'aria-hidden="TRUE"', 'style="display: none"',
                       'style="visibility: hidden"']:
            with self.subTest(hidden=hidden):
                html = f'<body><p>Visible listing</p><section {hidden}><p>Hidden listing</p></section></body>'
                self.assertEqual(clean_body_content(extract_body_content(html)), 'Visible listing')

    def test_inert_and_nested_hidden_content_is_removed(self):
        html = ('<body><p>Visible listing</p><div hidden><div hidden>Hidden listing</div></div>'
                '<noscript>Fallback listing</noscript><template>Template listing</template></body>')
        self.assertEqual(clean_body_content(extract_body_content(html)), 'Visible listing')

    def test_visible_siblings_and_normal_styles_survive(self):
        html = '<body><div hidden>Hidden listing</div><p style="display: block">Visible listing</p><p aria-hidden="false">Another listing</p></body>'
        self.assertEqual(clean_body_content(extract_body_content(html)), 'Visible listing\nAnother listing')

    def test_chunking_preserves_text(self):
        chunks = split_dom_content("abcdefgh", 3)
        self.assertEqual(chunks, ["abc", "def", "gh"])
        self.assertEqual("".join(chunks), "abcdefgh")

    def test_invalid_chunk_size_rejected(self):
        with self.assertRaises(ValueError):
            split_dom_content("text", 0)


if __name__ == "__main__":
    unittest.main()
