"""Search result parsing regression tests."""

from static_ai.skills.web import parse_results


def test_html_results_decode_redirect_and_snippet():
    body = b"""
    <div class="result">
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fguide">
        Example guide
      </a>
      <div class="result__snippet">Useful information</div>
    </div>
    """
    results = parse_results(body, "https://html.duckduckgo.com/html/")
    assert results == [
        {
            "title": "Example guide",
            "url": "https://example.com/guide",
            "snippet": "Useful information",
        }
    ]


def test_lite_results_and_duplicate_filtering():
    body = b"""
    <table>
      <tr><td><a class="result-link" href="https://example.com/a">First</a></td></tr>
      <tr><td><a class="result-link" href="https://example.com/a">Repeated</a></td></tr>
      <tr><td><a class="result-link" href="https://example.org/b">Second</a></td></tr>
    </table>
    """
    results = parse_results(body, "https://lite.duckduckgo.com/lite/")
    assert [item["title"] for item in results] == ["First", "Second"]


def test_ignores_search_engine_links():
    body = b'<a class="result__a" href="https://duckduckgo.com/about">About</a>'
    assert parse_results(body, "https://html.duckduckgo.com/html/") == []
