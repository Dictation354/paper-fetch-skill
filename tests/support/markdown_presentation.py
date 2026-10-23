"""Compare source text across valid Markdown and HTML presentations."""

from bs4 import BeautifulSoup
from markdown_it import MarkdownIt


def visible_markdown(text):
    soup = BeautifulSoup(MarkdownIt("commonmark", {"html": True}).render(text), "lxml")
    return " ".join(soup.get_text().split())
