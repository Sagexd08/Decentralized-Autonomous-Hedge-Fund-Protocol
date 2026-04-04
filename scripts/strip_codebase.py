from __future__ import annotations

import argparse
import io
import os
import re
import sys
import token
import tokenize
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCLUDES = {
    '.git',
    '.next',
    '.pytest_cache',
    '.venv',
    '__pycache__',
    'artifacts',
    'cache',
    'build',
    'coverage',
    'dist',
    'node_modules',
    'out',
    'vendor',
}

TEXT_EXTENSIONS = {
    '.css',
    '.env',
    '.example',
    '.go',
    '.html',
    '.java',
    '.js',
    '.json',
    '.jsx',
    '.mjs',
    '.md',
    '.py',
    '.rb',
    '.sh',
    '.sol',
    '.sql',
    '.ts',
    '.tsx',
    '.yaml',
    '.yml',
}

C_LIKE_EXTENSIONS = {'.c', '.cc', '.cpp', '.css', '.go', '.java', '.js', '.jsx', '.mjs', '.sol', '.ts', '.tsx'}
HASH_COMMENT_EXTENSIONS = {'.env', '.py', '.rb', '.sh', '.yaml', '.yml'}
SQL_EXTENSIONS = {'.sql'}
HTML_EXTENSIONS = {'.html'}
DOC_EXTENSIONS = {'.md'}
AGGRESSIVE_EXTENSIONS = {'.css', '.go', '.html', '.java', '.js', '.jsx', '.mjs', '.sol', '.sql', '.ts', '.tsx'}

def iter_files(root: Path, include_hidden: bool) -> Iterable[Path]:
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        rel_parts = current_path.relative_to(root).parts if current_path != root else ()

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if dirname not in DEFAULT_EXCLUDES
            and (include_hidden or not dirname.startswith('.'))
        ]

        if any(part in DEFAULT_EXCLUDES for part in rel_parts):
            continue
        if not include_hidden and any(part.startswith('.') for part in rel_parts):
            continue

        for filename in filenames:
            if not include_hidden and filename.startswith('.'):
                continue
            path = current_path / filename
            if path.suffix.lower() in TEXT_EXTENSIONS or path.name in {'Dockerfile'}:
                yield path

def strip_python_comments(source: str) -> str:
    reader = io.StringIO(source).readline
    out_tokens: list[tokenize.TokenInfo] = []
    try:
        for tok in tokenize.generate_tokens(reader):
            if tok.type == tokenize.COMMENT:
                continue
            out_tokens.append(tok)
        return tokenize.untokenize(out_tokens)
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source

_IDENTIFIER_RE = re.compile(r'[A-Za-z0-9_$]')

def _is_identifier_char(char: str) -> bool:
    return bool(char) and bool(_IDENTIFIER_RE.match(char))

def strip_c_like_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    state = 'code'
    string_delim = ''

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ''

        if state == 'code':
            if ch == '/' and nxt == '/':
                i += 2
                while i < n and source[i] != '\n':
                    i += 1
                continue
            if ch == '/' and nxt == '*':
                i += 2
                while i + 1 < n and not (source[i] == '*' and source[i + 1] == '/'):
                    i += 1
                i += 2 if i < n else 0
                continue
            if ch in {'"', "'", '`'}:
                state = 'string'
                string_delim = ch
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
            continue

        if state == 'string':
            out.append(ch)
            if ch == '\\' and i + 1 < n:
                out.append(source[i + 1])
                i += 2
                continue
            if ch == string_delim:
                state = 'code'
                string_delim = ''
            i += 1
            continue

    return ''.join(out)

def strip_hash_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    state = 'code'
    string_delim = ''

    while i < n:
        ch = source[i]

        if state == 'code':
            if ch == '#':
                while i < n and source[i] != '\n':
                    i += 1
                continue
            if ch in {'"', "'"}:
                state = 'string'
                string_delim = ch
                out.append(ch)
                i += 1
                continue
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        if ch == '\\' and i + 1 < n:
            out.append(source[i + 1])
            i += 2
            continue
        if ch == string_delim:
            state = 'code'
            string_delim = ''
        i += 1

    return ''.join(out)

def strip_sql_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    in_single = False
    in_double = False

    while i < n:
        ch = source[i]
        nxt = source[i + 1] if i + 1 < n else ''

        if not in_single and not in_double:
            if ch == '-' and nxt == '-':
                i += 2
                while i < n and source[i] != '\n':
                    i += 1
                continue
            if ch == '/' and nxt == '*':
                i += 2
                while i + 1 < n and not (source[i] == '*' and source[i + 1] == '/'):
                    i += 1
                i += 2 if i < n else 0
                continue

        out.append(ch)
        if ch == "'" and not in_double:
            if in_single and nxt == "'":
                out.append(nxt)
                i += 2
                continue
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        i += 1

    return ''.join(out)

def strip_html_comments(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    while i < n:
        if source.startswith('<!--', i):
            end = source.find('-->', i + 4)
            if end == -1:
                break
            i = end + 3
            continue
        out.append(source[i])
        i += 1
    return ''.join(out)

def cleanup_whitespace(source: str) -> str:
    lines = [line.rstrip() for line in source.splitlines()]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if line.strip() == '':
            blank_run += 1
            if blank_run > 1:
                continue
            cleaned.append('')
            continue
        blank_run = 0
        cleaned.append(line)
    text = '\n'.join(cleaned).strip() + '\n'
    return text

def aggressively_compact(source: str) -> str:
    out: list[str] = []
    i = 0
    n = len(source)
    state = 'code'
    string_delim = ''
    whitespace_pending = False

    while i < n:
        ch = source[i]

        if state == 'code':
            if ch in {'"', "'", '`'}:
                if whitespace_pending:
                    prev = out[-1] if out else ''
                    if _is_identifier_char(prev):
                        out.append(' ')
                    whitespace_pending = False
                out.append(ch)
                state = 'string'
                string_delim = ch
                i += 1
                continue
            if ch.isspace():
                whitespace_pending = True
                i += 1
                continue
            if whitespace_pending:
                prev = out[-1] if out else ''
                next_char = ch
                if _is_identifier_char(prev) and _is_identifier_char(next_char):
                    out.append(' ')
                whitespace_pending = False
            out.append(ch)
            i += 1
            continue

        out.append(ch)
        if ch == '\\' and i + 1 < n:
            out.append(source[i + 1])
            i += 2
            continue
        if ch == string_delim:
            state = 'code'
            string_delim = ''
        i += 1

    text = ''.join(out)
    text = re.sub(r'\n{2,}', '\n', text)
    return text.strip() + '\n'

def process_text(path: Path, source: str, mode: str) -> str:
    suffix = path.suffix.lower()
    name = path.name

    if suffix == '.py':
        stripped = strip_python_comments(source)
    elif suffix in C_LIKE_EXTENSIONS:
        stripped = strip_c_like_comments(source)
    elif suffix in HASH_COMMENT_EXTENSIONS or name == 'Dockerfile':
        stripped = strip_hash_comments(source)
    elif suffix in SQL_EXTENSIONS:
        stripped = strip_sql_comments(source)
    elif suffix in HTML_EXTENSIONS:
        stripped = strip_html_comments(source)
    elif suffix in DOC_EXTENSIONS:
        stripped = source
    else:
        stripped = source

    stripped = cleanup_whitespace(stripped)

    if mode == 'aggressive' and suffix in AGGRESSIVE_EXTENSIONS:
        stripped = aggressively_compact(stripped)

    return stripped

def main() -> int:
    parser = argparse.ArgumentParser(
        description='Remove comments and extra whitespace across the codebase.'
    )
    parser.add_argument('--root', default=str(ROOT), help='Root directory to process.')
    parser.add_argument(
        '--mode',
        choices={'safe', 'aggressive'},
        default='safe',
        help='safe removes comments + redundant whitespace; aggressive also compacts non-significant whitespace for some languages.',
    )
    parser.add_argument('--dry-run', action='store_true', help='Show files that would change without writing.')
    parser.add_argument('--include-hidden', action='store_true', help='Include dot-directories under the root.')
    args = parser.parse_args()

    root = Path(args.root).resolve()
    changed: list[Path] = []

    for path in iter_files(root, args.include_hidden):
        try:
            source = path.read_text(encoding='utf-8')
        except (OSError, UnicodeDecodeError):
            continue

        updated = process_text(path, source, args.mode)
        if updated == source:
            continue

        changed.append(path)
        if not args.dry_run:
            path.write_text(updated, encoding='utf-8', newline='\n')

    action = 'Would update' if args.dry_run else 'Updated'
    print(f'{action} {len(changed)} files in {root}')
    for path in changed:
        print(path.relative_to(root))

    if args.mode == 'aggressive':
        print('\nWarning: aggressive mode can still alter behavior in mixed-language repos. Review the diff before committing.', file=sys.stderr)

    return 0

if __name__ == '__main__':
    raise SystemExit(main())
