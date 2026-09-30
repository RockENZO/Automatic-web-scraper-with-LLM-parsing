"""Preserve semantic records and table headers in bounded model inputs."""
from dataclasses import dataclass
from bs4 import BeautifulSoup, Comment, NavigableString, Tag


@dataclass(frozen=True)
class Block:
    id: str
    text: str


def extract_blocks(html):
    soup = BeautifulSoup(html, 'html.parser')
    for tag in list(soup.find_all(['script', 'style', 'nav', 'noscript', 'template'])):
        tag.decompose()
    for tag in list(soup.find_all(True)):
        if tag.attrs is None:
            continue
        style = str(tag.get('style', '')).replace(' ', '').lower()
        if tag.has_attr('hidden') or str(tag.get('aria-hidden', '')).lower() == 'true' or 'display:none' in style or 'visibility:hidden' in style:
            tag.decompose()
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    texts = []

    def add(text):
        text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
        if text:
            texts.append(text)

    def visit(node):
        if isinstance(node, NavigableString):
            add(str(node))
            return
        if not isinstance(node, Tag):
            return
        if node.name == 'table':
            headers = None
            for row in node.find_all('tr'):
                cells = row.find_all(['th', 'td'], recursive=False)
                if not cells:
                    continue
                values = [cell.get_text(' ', strip=True) for cell in cells]
                if headers is None and all(cell.name == 'th' for cell in cells):
                    headers = values
                    continue
                if headers and len(headers) == len(values):
                    add('\n'.join(f'{header}: {value}' for header, value in zip(headers, values)))
                else:
                    add(' | '.join(values))
            return
        if node.name in ('article', 'li', 'p', 'address', 'pre', 'dt', 'dd', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6') or node.has_attr('data-record') or node.has_attr('itemscope'):
            if not node.find('table'):
                add(node.get_text('\n', strip=True))
                return
        for child in node.children:
            visit(child)

    visit(soup.body or soup)
    return [Block(f'b{index:04d}', text) for index, text in enumerate(texts, 1)]


def chunk_blocks(blocks, max_length=3000, overlap=200):
    if max_length < 100 or not 0 <= overlap < max_length // 2:
        raise ValueError('Invalid block chunk budget or overlap')
    chunks, current, used = [], [], 0
    for block in blocks:
        if not block.text.strip():
            continue
        # Long individual records use overlapping windows; ordinary records stay whole.
        start = 0
        while start < len(block.text):
            end = min(start + max_length - 40, len(block.text))
            if end < len(block.text):
                boundary = block.text.rfind('\n', start + (end-start)//2, end)
                if boundary < 0:
                    boundary = block.text.rfind(' ', start + (end-start)//2, end)
                if boundary > start:
                    end = boundary
            part = block.text[start:end]
            cost = len(part) + len(block.id) + 12
            if current and used + cost > max_length:
                chunks.append(current)
                current, used = [], 0
            current.append(Block(block.id, part))
            used += cost
            if end == len(block.text):
                break
            chunks.append(current)
            current, used = [], 0
            start = max(start + 1, end - overlap)
    if current:
        chunks.append(current)
    return chunks
