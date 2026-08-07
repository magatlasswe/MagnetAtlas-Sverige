"""Memory-bounded SQLite read adapter for the local web interface."""

from __future__ import annotations

from sqlalchemy import JSON, Column, Integer, MetaData, Table, func, select, text
from sqlalchemy.engine import ScalarResult
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.application.feature_queries import (
    DatasetSummary,
    ViewportResult,
)
from magnetatlas.application.features import (
    WORD_PATTERN,
    FeatureSearchFilters,
    feature_matches_search,
)
from magnetatlas.domain.features import AtlasFeature, FeatureId
from magnetatlas.domain.geography import BoundingBox
from magnetatlas.infrastructure.database.models import (
    AtlasFeatureRow,
    DatasetMetadataRow,
)
from magnetatlas.infrastructure.features.json_repository import feature_from_document

QUERY_METADATA = MetaData()
FTS = Table(
    "atlas_features_fts",
    QUERY_METADATA,
    Column("rowid", Integer, primary_key=True),
    Column("search_text"),
)


class SqlAlchemyFeatureQuerySource:
    """Query SQLite incrementally without constructing a global feature catalog."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        dataset_id: str,
    ) -> None:
        self._session_factory = session_factory
        self._dataset_id = dataset_id

    def summary(self) -> DatasetSummary:
        with self._session_factory() as session:
            count = int(
                session.scalar(
                    select(func.count())
                    .select_from(AtlasFeatureRow)
                    .where(AtlasFeatureRow.dataset_id == self._dataset_id)
                )
                or 0
            )
            metadata = session.get(DatasetMetadataRow, self._dataset_id)
            source = session.scalar(
                select(AtlasFeatureRow.source)
                .where(AtlasFeatureRow.dataset_id == self._dataset_id)
                .order_by(AtlasFeatureRow.id)
                .limit(1)
            )
        return DatasetSummary(
            count=count,
            latest_import=metadata.base_imported_at if metadata is not None else None,
            source=source,
            status="Officiell" if count else "Tom",
        )

    def _rows(self, session: Session) -> ScalarResult[AtlasFeatureRow]:
        statement = (
            select(AtlasFeatureRow)
            .where(AtlasFeatureRow.dataset_id == self._dataset_id)
            .order_by(AtlasFeatureRow.id)
            .execution_options(yield_per=500)
        )
        return session.scalars(statement)

    def in_bounds(self, bounds: BoundingBox, *, limit: int) -> ViewportResult:
        statement = text(
            "SELECT af.document AS document FROM atlas_features_rtree r "
            "CROSS JOIN atlas_features af ON af.id=r.id "
            "WHERE r.min_longitude <= :east AND r.max_longitude >= :west "
            "AND r.min_latitude <= :north AND r.max_latitude >= :south "
            "AND af.dataset_id=:dataset_id LIMIT :limit"
        ).columns(document=JSON)
        with self._session_factory() as session:
            documents = session.scalars(
                statement,
                {
                    "east": bounds.east,
                    "west": bounds.west,
                    "north": bounds.north,
                    "south": bounds.south,
                    "dataset_id": self._dataset_id,
                    "limit": limit + 1,
                },
            ).all()
        features = tuple(
            feature_from_document(document) for document in documents[:limit]
        )
        return ViewportResult(features, len(documents) > limit)

    def viewport_query_plan(
        self, bounds: BoundingBox, *, limit: int = 100
    ) -> tuple[str, ...]:
        """Return SQLite's diagnostic plan for the indexed viewport query."""
        statement = text(
            "EXPLAIN QUERY PLAN SELECT af.document FROM atlas_features_rtree r "
            "CROSS JOIN atlas_features af ON af.id=r.id "
            "WHERE r.min_longitude <= :east AND r.max_longitude >= :west "
            "AND r.min_latitude <= :north AND r.max_latitude >= :south "
            "AND af.dataset_id=:dataset_id LIMIT :limit"
        )
        with self._session_factory() as session:
            rows = session.execute(
                statement,
                {
                    "east": bounds.east,
                    "west": bounds.west,
                    "north": bounds.north,
                    "south": bounds.south,
                    "dataset_id": self._dataset_id,
                    "limit": limit + 1,
                },
            )
            return tuple(str(row[3]) for row in rows)

    def get(self, feature_id: FeatureId | str) -> AtlasFeature:
        normalized = str(feature_id)
        with self._session_factory() as session:
            document = session.scalar(
                select(AtlasFeatureRow.document).where(
                    AtlasFeatureRow.dataset_id == self._dataset_id,
                    AtlasFeatureRow.feature_id == normalized,
                )
            )
        if not isinstance(document, dict):
            raise KeyError(f"Okänd AtlasFeature: {normalized}")
        return feature_from_document(document)

    def search(
        self,
        query: str,
        *,
        filters: FeatureSearchFilters,
        limit: int,
    ) -> tuple[AtlasFeature, ...]:
        terms = WORD_PATTERN.findall(query.casefold())
        statement = select(AtlasFeatureRow)
        if terms:
            expression = " ".join(f'"{term}"*' for term in terms)
            statement = statement.join(FTS, FTS.c.rowid == AtlasFeatureRow.id).where(
                FTS.c.search_text.match(expression)
            )
        statement = statement.where(AtlasFeatureRow.dataset_id == self._dataset_id)
        if filters.sources:
            statement = statement.where(AtlasFeatureRow.source.in_(filters.sources))
        if filters.feature_types:
            statement = statement.where(
                AtlasFeatureRow.feature_type.in_(filters.feature_types)
            )
        statement = statement.execution_options(yield_per=500)
        matches: list[AtlasFeature] = []
        with self._session_factory() as session:
            candidates = session.scalars(statement)
            found_candidate = False
            for row in candidates:
                found_candidate = True
                feature = feature_from_document(row.document)
                if feature_matches_search(feature, query, filters):
                    matches.append(feature)
                    if len(matches) == limit:
                        break
            if terms and not found_candidate:
                for row in self._rows(session):
                    feature = feature_from_document(row.document)
                    if feature_matches_search(feature, query, filters):
                        matches.append(feature)
                        if len(matches) == limit:
                            break
        return tuple(matches)
