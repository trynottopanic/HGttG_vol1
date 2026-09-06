import json
import unittest

import guide_wikipedia_client as client


class FakeResponse:
    def __init__(self, document):
        self.body = json.dumps(document).encode("utf-8")
        self.headers = {"Content-Length": str(len(self.body))}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, limit):
        return self.body[:limit]


def opening(document, observations):
    def open_request(request, timeout):
        observations.append((request, timeout))
        return FakeResponse(document)
    return open_request


class WikipediaClientTests(unittest.TestCase):
    def test_search_returns_bounded_plain_fields(self):
        observations = []
        document = {"query": {"search": [
            {"pageid": 12, "title": "Earth", "wordcount": 1000, "snippet": "ignored"}
        ]}}
        result = client.search("earth", opening(document, observations))
        self.assertEqual(result, [{"pageid": 12, "title": "Earth", "wordcount": 1000}])
        request, timeout = observations[0]
        self.assertIn("srsearch=earth", request.full_url)
        self.assertEqual(request.get_header("User-agent"), client.USER_AGENT)
        self.assertEqual(timeout, client.TIMEOUT_SECONDS)

    def test_article_returns_plain_text_and_attribution(self):
        observations = []
        document = {"parse": {
            "pageid": 12,
            "title": "Earth",
            "displaytitle": "Earth",
            "text": '<div class="shortdescription">Ignored</div><p>Earth is the third <a href="./Planet">planet</a> from the Sun.</p><h2>History<span class="mw-editsection"><a href="./Help">edit</a></span></h2><p>Old.</p>'
        }}
        result = client.article("Earth", opening(document, observations))
        self.assertEqual(result["title"], "Earth")
        self.assertIn("third planet", result["text"])
        self.assertIn("[ HISTORY ]\n\nOld.", result["text"])
        self.assertEqual(result["links"], ["Planet"])
        self.assertIn("planet [1]", result["text"])
        self.assertNotIn("Ignored", result["text"])
        self.assertNotIn("edit", result["text"])
        self.assertIn("CC BY-SA", result["license"])
        self.assertIn("action=parse", observations[0][0].full_url)

    def test_blank_search_is_rejected_without_network(self):
        with self.assertRaises(client.WikipediaClientError):
            client.search("   ", lambda *_: self.fail("network should not be called"))

    def test_oversized_response_is_rejected(self):
        class TooLarge:
            headers = {"Content-Length": str(client.MAX_RESPONSE_BYTES + 1)}
            def __enter__(self): return self
            def __exit__(self, *_): return False
        with self.assertRaises(client.WikipediaClientError):
            client.search("earth", lambda *_args, **_kwargs: TooLarge())


if __name__ == "__main__":
    unittest.main()
