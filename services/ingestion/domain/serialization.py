from services.ingestion.domain.document import CanonicalDocument
from services.ingestion.domain.elements import (
    DocumentElement,
    ElementType,
    TableData,
)


def document_to_dict(document: CanonicalDocument) -> dict:
    return {
        "title": document.title,
        "page_count": document.page_count,
        "metadata": document.metadata,
        "elements": [
            {
                "element_type": element.element_type.value,
                "text": element.text,
                "page_start": element.page_start,
                "page_end": element.page_end,
                "section_path": element.section_path,
                "metadata": element.metadata,
                "table": (
                    {
                        "headers": element.table.headers,
                        "rows": element.table.rows,
                    }
                    if element.table
                    else None
                ),
            }
            for element in document.elements
        ],
    }


def document_from_dict(data: dict) -> CanonicalDocument:
    elements = []

    for item in data["elements"]:
        table_data = item.get("table")

        table = (
            TableData(
                headers=table_data.get("headers", []),
                rows=table_data.get("rows", []),
            )
            if table_data
            else None
        )

        elements.append(
            DocumentElement(
                element_type=ElementType(item["element_type"]),
                text=item["text"],
                page_start=item.get("page_start"),
                page_end=item.get("page_end"),
                section_path=item.get("section_path", []),
                metadata=item.get("metadata", {}),
                table=table,
            )
        )

    return CanonicalDocument(
        title=data["title"],
        elements=elements,
        page_count=data.get("page_count", 0),
        metadata=data.get("metadata", {}),
    )
