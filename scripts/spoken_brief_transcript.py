"""Versioned, bounded word comparison; never a voice-quality certificate."""
from __future__ import annotations

import copy
import re
import unicodedata

from spoken_brief_compile import SPEAKER_RE, SpokenBriefError, canonical_digest, digest_bytes

NORMALIZATION_VERSION = 1
MAX_TEXT_CHARS = 200000
MAX_WORDS = 16000
MAX_ALIGNMENT_CELLS = 4000000
MAX_LEXICON_ENTRIES = 128
EMPTY_LEXICON = {'schema_version': 1, 'id': 'empty', 'revision': 1, 'entries': []}
TOKEN = re.compile(r"(?<!\w)[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?(?!\w)|[^\W_]+(?:'[^\W_]+)*|(?<!\w)-(?=\s*[0-9])|[%+/\\]")
SMALL = 'zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split()
TENS = 'zero ten twenty thirty forty fifty sixty seventy eighty ninety'.split()


def _text(value):
    if not isinstance(value, str) or len(value) > MAX_TEXT_CHARS or '\0' in value:
        raise SpokenBriefError('Transcript must be bounded text without NUL characters')
    try: value.encode('utf-8')
    except UnicodeError as exc: raise SpokenBriefError('Transcript must be valid UTF-8 text') from exc
    return value


def _cardinal(number):
    if number < 20: return [SMALL[number]]
    if number < 100: return [TENS[number // 10]] + (_cardinal(number % 10) if number % 10 else [])
    if number < 1000: return _cardinal(number // 100) + ['hundred'] + (_cardinal(number % 100) if number % 100 else [])
    return _cardinal(number // 1000) + ['thousand'] + (_cardinal(number % 1000) if number % 1000 else [])


def _base(text):
    text = unicodedata.normalize('NFKC', _text(text)).casefold().replace('’', "'")
    words = []
    for token in TOKEN.findall(text):
        if re.fullmatch(r'[0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?', token):
            whole, dot, fraction = token.replace(',', '').partition('.')
            if len(whole) <= 6 and not (len(whole) > 1 and whole.startswith('0')):
                words.extend(_cardinal(int(whole)))
            else:
                words.extend(SMALL[int(x)] for x in whole)
            if dot: words.extend(['point', *(SMALL[int(x)] for x in fraction)])
        else:
            words.append({'-': 'minus', '+': 'plus', '%': 'percent', '/': 'slash', '\\': 'backslash'}.get(token, token))
        if len(words) > MAX_WORDS: raise SpokenBriefError('Normalized transcript word budget exceeded')
    return words


def validate_lexicon(value=None):
    value = EMPTY_LEXICON if value is None else value
    if (not isinstance(value, dict) or set(value) != {'schema_version', 'id', 'revision', 'entries'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1
            or not isinstance(value['id'], str) or not SPEAKER_RE.fullmatch(value['id'])
            or type(value['revision']) is not int or not 1 <= value['revision'] <= 1000000
            or not isinstance(value['entries'], list) or len(value['entries']) > MAX_LEXICON_ENTRIES):
        raise SpokenBriefError('Lexicon requires an exact versioned, bounded schema')
    seen = set()
    for entry in value['entries']:
        if (not isinstance(entry, dict) or set(entry) != {'written', 'spoken'}
                or any(not isinstance(x, str) or not 1 <= len(x) <= 200 for x in entry.values())):
            raise SpokenBriefError('Invalid pronunciation lexicon entry')
        source, target = tuple(_base(entry['written'])), _base(entry['spoken'])
        if not source or not target or len(source) > 32 or len(target) > 32 or source in seen:
            raise SpokenBriefError('Lexicon contains an empty, oversized or ambiguous normalized entry')
        seen.add(source)
    return copy.deepcopy(value)


def normalize(text, lexicon=None):
    """NFKC/casefold, punctuation, cardinal numbers, then one longest-match pass.

    Lexicon substitutions are explicit comparison aliases, not edits to the
    authoritative Markdown or instructions to synthesize different words.
    """
    book = validate_lexicon(lexicon)
    rules = {}
    for entry in book['entries']:
        source, target = _base(entry['written']), _base(entry['spoken'])
        rules.setdefault(source[0], []).append((source, target))
    for group in rules.values(): group.sort(key=lambda x: (-len(x[0]), x[0]))
    source = _base(text); result = []; index = 0
    while index < len(source):
        for written, spoken in rules.get(source[index], []):
            if source[index:index + len(written)] == written:
                result.extend(spoken); index += len(written); break
        else:
            result.append(source[index]); index += 1
        if len(result) > MAX_WORDS: raise SpokenBriefError('Lexicon expansion exceeded the word budget')
    return result


def compare_text(expected, observed, lexicon=None):
    """Exact Levenshtein edits with deterministic diagonal/deletion/insertion ties.

    Refuse quadratic work beyond the fixed cell budget without pretending a
    truncated comparison succeeded. Exact long transcripts use a linear fast path.
    """
    left, right = normalize(expected, lexicon), normalize(observed, lexicon)
    n, m = len(left), len(right)
    result = {'normalization_version': NORMALIZATION_VERSION,
        'expected_words': n, 'observed_words': m,
        'expected_normalized_sha256': canonical_digest(left), 'observed_normalized_sha256': canonical_digest(right),
        'counts': {'substitution': 0, 'insertion': 0, 'deletion': 0}, 'edits': [], 'word_error_rate': None}
    if left == right:
        result.update(status='match' if n else 'empty', word_error_rate=0 if n else None)
        return result
    if (n + 1) * (m + 1) > MAX_ALIGNMENT_CELLS:
        result.update(status='unaligned-budget', counts=None)
        return result
    width = m + 1
    trace = bytearray((n + 1) * width)
    trace[1:width] = bytes([3]) * m
    previous = list(range(width))
    for i, word in enumerate(left, 1):
        current = [i] + [0] * m; trace[i * width] = 2
        for j, other in enumerate(right, 1):
            diagonal = previous[j - 1] + (word != other)
            deletion, insertion = previous[j] + 1, current[j - 1] + 1
            best = min(diagonal, deletion, insertion)
            current[j] = best
            trace[i * width + j] = 1 if best == diagonal else (2 if best == deletion else 3)
        previous = current
    i, j = n, m
    while i or j:
        op = trace[i * width + j]
        if op == 1:
            i -= 1; j -= 1
            if left[i] == right[j]: continue
            kind, want, actual = 'substitution', left[i], right[j]
        elif op == 2:
            i -= 1; kind, want, actual = 'deletion', left[i], None
        else:
            j -= 1; kind, want, actual = 'insertion', None, right[j]
        result['counts'][kind] += 1
        result['edits'].append({'op': kind, 'expected_index': i, 'observed_index': j, 'expected': want, 'observed': actual})
    result['edits'].reverse()
    result.update(status='empty' if not right else 'differences',
                  word_error_rate=sum(result['counts'].values()) / n if n else None)
    return result
