import os
import shutil
import tempfile

from contextlib import contextmanager
from pathlib import Path
from typing import IO
from collections.abc import Callable, Generator
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, url2pathname, urlopen


class URLResourceError(Exception):
    pass

@contextmanager
def _open_url_resource(url: str, timeout: float = 30.0) -> Generator[tuple[IO[bytes], Path | None], None, None]:
    parsed = urlparse(url)
    local_path = None
    stream = None

    try:
        if parsed.scheme == 'file':
            local_path = Path(url2pathname(parsed.path))
            stream = local_path.open('rb')

        elif parsed.scheme in ('http', 'https'):
            req = Request(url)
            stream = urlopen(req, timeout=timeout)
  
        else:
            raise URLResourceError(f"Unsupported URI protocol '{parsed.scheme}://'")

    except HTTPError as e:
        raise URLResourceError(f"HTTP Error:\n{e.code} {e.reason}") from e
    except URLError as e:
        raise URLResourceError(f"URL/Connection Error:\n{e.reason}") from e

    except TimeoutError as e:
        raise URLResourceError(f"Socket Timeout:\n{e}") from e
    except PermissionError as e:
        raise URLResourceError(f"Permission Error:\n{e}") from e

    except FileNotFoundError as e:
        raise URLResourceError(f"Local file '{url}' does not exist.") from e
    except IsADirectoryError as e:
        raise URLResourceError(f"Provided URL '{url}' points to a directory istead of a file.") from e

    try:
        yield stream, local_path
    finally:
        if stream is not None:
            stream.close()


def fetch_text(url: str, encoding: str = 'utf-8') -> str:
    try:
        with _open_url_resource(url) as (stream, _):
            content = stream.read()
            return content.decode(encoding)

    except UnicodeDecodeError as e:
        raise URLResourceError(f"Could not decode content using {encoding}:\n{e}") from e


ReportHook = Callable[[int, int, int], None]

def _copy_with_report(
    src: IO[bytes],
    dst: IO[bytes],
    total_size: int | None,
    reporthook: ReportHook | None = None,
    chunk_size: int = 64 * 1024) -> None:
    if reporthook is None or total_size is None:
        shutil.copyfileobj(src, dst, length=chunk_size)
        return

    block_count = 0
    reporthook(block_count, chunk_size, total_size)

    while True:
        chunk = src.read(chunk_size)
        if not chunk:
            break

        dst.write(chunk)
        block_count += 1
        reporthook(block_count, chunk_size, total_size)

def _get_total_size(stream: IO[bytes]) -> int | None:
    headers = getattr(stream, "headers", None)
    if headers:
        content_length = headers.get("Content-Length")
        if content_length and content_length.isdigit():
            return int(content_length)

    return None

def download_to_file(url: str, dest_path: Path | None = None, reporthook: ReportHook | None = None) -> tuple[Path, bool]:
    try:
        with _open_url_resource(url) as (stream, local_file):
            if local_file and dest_path is None:
                return (local_file, True)

            temp_file_path = None
            with tempfile.NamedTemporaryFile(prefix=f"renode-run-{os.getpid()}-", delete=False) as temp_file:
                total_size = None
                if local_file:
                    reporthook = None
                else:
                    total_size = _get_total_size(stream)

                _copy_with_report(stream, temp_file.file, total_size, reporthook)
                temp_file_path = Path(temp_file.name)

            if not dest_path:
                return (temp_file_path, False)
            else:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(temp_file_path, dest_path)
                return (dest_path, False)

    except PermissionError as e:
        raise URLResourceError(f"Permission denied on file download:\n{e}") from e
    except OSError as e:
        raise URLResourceError(f"Could not download a file:\n{e}") from e
