class RetrievalReranker:

    def rank(self, results, top_k: int = 5):
        if not results:
            return []

        deduplicated = self._deduplicate(results)

        by_source = {}
        for result in deduplicated:
            by_source.setdefault(result.source, []).append(result)

        for source_results in by_source.values():
            source_results.sort(
                key=lambda result: result.score,
                reverse=True,
            )

        ranked = self._interleave(by_source)

        return ranked[:top_k]

    @staticmethod
    def _deduplicate(results):
        seen = set()
        deduplicated = []

        for result in results:
            key = (
                result.document_version_id,
                result.chunk_id,
            )

            if key in seen:
                continue

            seen.add(key)
            deduplicated.append(result)

        return deduplicated

    @staticmethod
    def _interleave(by_source):
        ranked = []
        index = 0

        sources = list(by_source)

        while True:
            added = False

            for source in sources:
                source_results = by_source[source]

                if index < len(source_results):
                    ranked.append(source_results[index])
                    added = True

            if not added:
                break

            index += 1

        return ranked
