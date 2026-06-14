import re

WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]]+)\]\]")


def extract_wiki_links(content: str) -> list[str]:
    return WIKI_LINK_PATTERN.findall(content)


def normalize_wiki_target(raw_target: str) -> str:
    return raw_target.split("|", 1)[0].split("#", 1)[0].strip()
