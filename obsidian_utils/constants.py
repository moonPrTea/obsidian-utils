import re


TAG_PATTERN = re.compile(r'(?<![\w/#\\])#([\w/-]+)', re.UNICODE)
WIKI_LINK_PATTERN = re.compile(r'!?\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
MARKDOWN_LINK_PATTERN = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')
COMMENT_PATTERN = re.compile(r'<!--.*?-->|%%.*?%%', re.S)
CODE_FENCE_PATTERN = re.compile(r'^\s{0,3}(`{3,}|~{3,})(.*)$')
INLINE_CODE_PATTERN = re.compile(r'(`+).*?\1', re.S)
TAG_SEPARATOR_PATTERN = re.compile(r'[,\s]+')
URL_PATTERN = re.compile(r'https?://\S+')


DEFAULT_CONFIG_FILE = 'config-f.md'
MIN_CONTENT_WORDS = 5
TABLE_SEPARATOR_PATTERN = re.compile(r'(?<!\\)\|')
HEADING_PATTERN = re.compile(r'^\s*#{1,6}\s+.*$', re.M)
CONTENT_WORD_PATTERN = re.compile(r'\b\w+\b')


DEFAULT_THRESHOLD = 0.75
MIN_LABEL_EXAMPLES = 2
MAX_FEATURES = 20000
MAX_ITERATIONS = 1000
NGRAM_RANGE = (1, 2)
RANDOM_STATE = 42


MIN_EVALUATION_NOTES = 8
TEST_SIZE = 0.25
