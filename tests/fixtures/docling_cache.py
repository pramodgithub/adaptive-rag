from pathlib import Path

from docling.document_converter import DocumentConverter
from docling_core.types.doc.document import DoclingDocument


CACHE_DIR = Path("/app/tests/data/cache")


def get_cache_path(pdf_path: str | Path) -> Path:
    pdf_path = Path(pdf_path)
    name = pdf_path.name
    if name.endswith(".docling.json"):
        name = name[: -len(".docling.json")]
    else:
        name = pdf_path.stem
    return CACHE_DIR / f"{name}.docling.json"


def cache_exists(pdf_path: str | Path) -> bool:
    return get_cache_path(pdf_path).exists()


def create_cache(pdf_path: str | Path) -> Path:
    pdf_path = Path(pdf_path)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    cache_path = get_cache_path(pdf_path)

    converter = DocumentConverter()
    result = converter.convert(str(pdf_path))

    result.document.save_as_json(
        str(cache_path),
        indent=2,
    )

    return cache_path


def load_cached_document(pdf_path: str | Path) -> DoclingDocument:
    cache_path = get_cache_path(pdf_path)

    if not cache_path.exists():
        raise FileNotFoundError(
            f"Docling cache not found: {cache_path}"
        )

    return DoclingDocument.load_from_json(str(cache_path))


def load_or_create_document(
    pdf_path: str | Path,
) -> tuple[DoclingDocument, bool]:
    if cache_exists(pdf_path):
        return load_cached_document(pdf_path), False

    cache_path = create_cache(pdf_path)
    return load_cached_document(pdf_path), True
