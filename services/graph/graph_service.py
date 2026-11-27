import hashlib
import re

from neo4j import GraphDatabase

from core.config.settings import settings


# Link types written by this service, with the node labels they connect.
_LINKS = {
    "HAS_SECTION": ("DocumentVersion", "Section"),
    "HAS_SUBSECTION": ("Section", "Section"),
    "IN_SECTION": ("Chunk", "Section"),
    "NEXT": ("Chunk", "Chunk"),
    "PART_OF": ("Chunk", "Chunk"),
}


# A section's identity comes from its own title only ("Article 32: ...",
# "SECTION 3-...", "CHAPTER IV: ..."). Unnumbered titles get none.
_TITLE_ID = re.compile(
    r"^\s*(article|section|chapter|part|annex|appendix|schedule|clause)"
    r"\s+([\dIVXLC]+[a-z]?)(?![\w.])",
    re.IGNORECASE,
)


def _title_identity(title: str) -> tuple[str | None, str | None]:
    match = _TITLE_ID.match(title or "")
    if not match:
        return None, None
    return match.group(1).lower(), match.group(2)


class GraphService:
    def __init__(self):
        self.driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(
                settings.NEO4J_USERNAME,
                settings.NEO4J_PASSWORD,
            ),
        )

    def close(self):
        self.driver.close()

    def create_document_graph(self, document, document_version, chunks):
        tree = self.build_tree(str(document_version.id), chunks)

        with self.driver.session() as session:
            session.execute_write(
                self._create_graph,
                document,
                document_version,
                tree,
            )

        return tree["counts"]

    @staticmethod
    def build_tree(version_id: str, chunks) -> dict:
        """Build the graph as plain lists. No database needed, so tests
        can check the tree on cached documents.

        Sections come from each chunk's section_path. Control chunks link
        to their parent control through parent_identifier.
        """
        ordered = sorted(chunks, key=lambda chunk: chunk.chunk_index)

        def chunk_id(chunk) -> str:
            value = getattr(chunk, "id", None)
            return str(value) if value is not None else f"{version_id}:c:{chunk.chunk_index}"

        def section_id(path: tuple[str, ...]) -> str:
            digest = hashlib.sha1("␟".join(path).encode("utf-8")).hexdigest()
            return f"{version_id}:s:{digest[:16]}"

        sections: dict[tuple[str, ...], dict] = {}
        chunk_nodes: list[dict] = []
        links: dict[str, list[tuple[str, str]]] = {name: [] for name in _LINKS}

        for chunk in ordered:
            path = tuple(part for part in (chunk.section_path or []) if part)

            for depth in range(1, len(path) + 1):
                prefix = path[:depth]

                if prefix in sections:
                    continue

                own_type, own_id = _title_identity(prefix[-1])
                sections[prefix] = {
                    "id": section_id(prefix),
                    "version_id": version_id,
                    "title": prefix[-1],
                    "depth": depth,
                    "path": list(prefix),
                    "identifier": own_id,
                    "structure_type": own_type,
                }

                if depth == 1:
                    links["HAS_SECTION"].append((version_id, sections[prefix]["id"]))
                else:
                    links["HAS_SUBSECTION"].append(
                        (sections[prefix[:-1]]["id"], sections[prefix]["id"])
                    )

            chunk_nodes.append({
                "id": chunk_id(chunk),
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "page_start": chunk.page_start,
                "page_end": chunk.page_end,
                "section_path": list(path),
                "structure_type": chunk.structure_type,
                "identifier": chunk.identifier,
                "parent_identifier": chunk.parent_identifier,
            })

            if path:
                links["IN_SECTION"].append((chunk_id(chunk), sections[path]["id"]))

                # A section takes the identity of the chunks directly in it
                # (an Article section gets "32"). Control rows are their own
                # nodes, so they don't name the section.
        for current, following in zip(ordered, ordered[1:]):
            links["NEXT"].append((chunk_id(current), chunk_id(following)))

        controls: dict[str, str] = {}
        for chunk in ordered:
            if chunk.structure_type == "control" and chunk.identifier:
                controls.setdefault(chunk.identifier, chunk_id(chunk))

        for chunk in ordered:
            parent = controls.get(chunk.parent_identifier or "")
            if (
                chunk.structure_type == "control"
                and parent
                and parent != chunk_id(chunk)
            ):
                links["PART_OF"].append((chunk_id(chunk), parent))

        return {
            "version_id": version_id,
            "sections": list(sections.values()),
            "chunks": chunk_nodes,
            "links": {
                name: [{"source": a, "target": b} for a, b in pairs]
                for name, pairs in links.items()
            },
            "counts": {
                "sections": len(sections),
                "chunks": len(chunk_nodes),
                **{name.lower(): len(pairs) for name, pairs in links.items()},
            },
        }

    @staticmethod
    def _create_graph(tx, document, document_version, tree):
        version_id = tree["version_id"]

        tx.run(
            """
            MERGE (d:Document {id: $document_id})
            SET d.title = $title,
                d.source = $source,
                d.document_type = $document_type

            MERGE (v:DocumentVersion {id: $version_id})
            SET v.version = $version

            MERGE (d)-[:HAS_VERSION]->(v)
            """,
            document_id=str(document.id),
            title=document.title,
            source=document.source,
            document_type=document.document_type,
            version_id=version_id,
            version=document_version.version,
        )

        # Rebuild cleanly: remove only what this service builds for this
        # version. Chunk nodes and anything else in Neo4j stay.
        tx.run(
            """
            MATCH (:DocumentVersion {id: $version_id})-[:HAS_CHUNK]->(c:Chunk)
                  -[r:IN_SECTION|NEXT|PART_OF]->()
            DELETE r
            """,
            version_id=version_id,
        )
        tx.run(
            "MATCH (s:Section {version_id: $version_id}) DETACH DELETE s",
            version_id=version_id,
        )

        tx.run(
            """
            UNWIND $chunks AS chunk
            MERGE (c:Chunk {id: chunk.id})
            SET c += chunk
            WITH c
            MATCH (v:DocumentVersion {id: $version_id})
            MERGE (v)-[:HAS_CHUNK]->(c)
            """,
            chunks=tree["chunks"],
            version_id=version_id,
        )

        tx.run(
            """
            UNWIND $sections AS section
            MERGE (s:Section {id: section.id})
            SET s += section
            """,
            sections=tree["sections"],
        )

        for name, (source_label, target_label) in _LINKS.items():
            pairs = tree["links"][name]

            if not pairs:
                continue

            tx.run(
                f"""
                UNWIND $pairs AS pair
                MATCH (a:{source_label} {{id: pair.source}})
                MATCH (b:{target_label} {{id: pair.target}})
                MERGE (a)-[:{name}]->(b)
                """,
                pairs=pairs,
            )