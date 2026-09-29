"""HTML extraction and chunking without browser or model dependencies."""

from bs4 import BeautifulSoup, Comment


def extract_body_content(html_content):
    """Return the body markup, or an empty string when there is no body."""
    body = BeautifulSoup(html_content, "html.parser").body
    return str(body) if body else ""


def clean_body_content(body_content):
    """Extract readable body text, omitting navigation and hidden markup."""
    soup = BeautifulSoup(body_content, "html.parser")
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()
    for comment in soup.find_all(string=lambda value: isinstance(value, Comment)):
        comment.extract()
    lines = (line.strip() for line in soup.get_text(separator="\n").splitlines())
    return "\n".join(line for line in lines if line and len(line) > 2)


def split_dom_content(dom_content, max_length=6000):
    """Split text into ordered chunks of at most max_length characters."""
    if max_length <= 0:
        raise ValueError("max_length must be positive")
    return [dom_content[i:i + max_length]
            for i in range(0, len(dom_content), max_length)] or [""]
