"""Memory-bounded SQLite read adapter for the local web interface."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from magnetatlas.application.feature_queries import (
    DatasetSummary,
    ViewportResult,
    intersects_bounds,
)
from magnetatlas.application.features import (
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
            first_document = session.scalar(
                select(AtlasFeatureRow.document)
                .where(AtlasFeatureRow.dataset_id == self._dataset_id)
                .order_by(AtlasFeatureRow.id)
                .limit(1)
            )
        source = None
        if isinstance(first_document, dict):
            provenance = first_document.get("provenance")
            if isinstance(provenance, dict):
                value = provenance.get("source")
                source = value if isinstance(value, str) else None
        return DatasetSummary(
            count=count,
            latest_import=metadata.base_imported_at if metadata is not None else None,
            source=source,
            status="RAÄ" if count else "Tom",
        )

    def _rows(self, session: Session):  # type: ignore[no-untyped-def]
        statement = (
            select(AtlasFeatureRow)
            .where(AtlasFeatureRow.dataset_id == self._dataset_id)
            .order_by(AtlasFeatureRow.id)
            .execution_options(yield_per=500)
        )
        return session.scalars(statement)

    def in_bounds(self, bounds: BoundingBox, *, limit: int) -> ViewportResult:
        matches: list[AtlasFeature] = []
        truncated = False
        with self._session_factory() as session:
            for row in self._rows(session):
                feature = feature_from_document(row.document)
                if not intersects_bounds(feature, bounds):
                    continue
                if len(matches) == limit:
                    truncated = True
                    break
                matches.append(feature)
        return ViewportResult(tuple(matches), truncated)

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
        matches: list[AtlasFeature] = []
        with self._session_factory() as session:
            for row in self._rows(session):
                feature = feature_from_document(row.document)
                if feature_matches_search(feature, query, filters):
                    matches.append(feature)
                    if len(matches) == limit:
                        break
        return tuple(matches)
