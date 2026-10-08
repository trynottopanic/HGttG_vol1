import unittest

import guide_wikipedia_netsurf as gateway
from guide_wikipedia_client import WikipediaClientError


class FakeImageResponse:
    def __init__(self, body=b"image", content_type="image/png", url="https://upload.wikimedia.org/a.png"):
        self.body = body
        self.headers = {"Content-Type": content_type, "Content-Length": str(len(body))}
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def geturl(self):
        return self.url

    def read(self, limit):
        return self.body[:limit]


class WikipediaNetSurfTests(unittest.TestCase):
    def test_image_proxy_accepts_bounded_wikimedia_image(self):
        content_type, body = gateway.fetch_image(
            "https://upload.wikimedia.org/a.png",
            lambda request, timeout: FakeImageResponse(),
        )
        self.assertEqual(content_type, "image/png")
        self.assertEqual(body, b"image")

    def test_image_proxy_rejects_other_origins_before_network(self):
        with self.assertRaises(WikipediaClientError):
            gateway.fetch_image(
                "https://example.test/tracker.png",
                lambda *_args, **_kwargs: self.fail("network should not be called"),
            )

    def test_image_proxy_rejects_redirect_away_from_wikimedia(self):
        with self.assertRaises(WikipediaClientError):
            gateway.fetch_image(
                "https://upload.wikimedia.org/a.png",
                lambda *_args, **_kwargs: FakeImageResponse(url="https://example.test/a.png"),
            )

    def test_image_proxy_rejects_oversized_body(self):
        response = FakeImageResponse(body=b"x" * (gateway.MAX_IMAGE_BYTES + 1))
        with self.assertRaises(WikipediaClientError):
            gateway.fetch_image(
                "https://upload.wikimedia.org/a.png",
                lambda *_args, **_kwargs: response,
            )


if __name__ == "__main__":
    unittest.main()
