import re


TAG_PATTERN = re.compile(r'(?<![\w/#\\])#([\w/-]+)', re.UNICODE)
WIKI_LINK_PATTERN = re.compile(r'!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
COMMENT_PATTERN = re.compile(r'<!--.*?-->|%%.*?%%', re.S)
CODE_FENCE_PATTERN = re.compile(r'^\s{0,3}(`{3,}|~{3,})(.*)$')
INLINE_CODE_PATTERN = re.compile(r'(`+).*?\1', re.S)
TAG_SEPARATOR_PATTERN = re.compile(r'[,\s]+')
URL_PATTERN = re.compile(r'https?://\S+')
