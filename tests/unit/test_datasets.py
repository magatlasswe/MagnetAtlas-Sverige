"""Tests for source, imported dataset and geographical scope identities."""

import pytest

from magnetatlas.domain.datasets import DatasetInstance, DatasetScope, SourceDefinition
from magnetatlas.domain.geography import BoundingBox

SOURCE = SourceDefinition("raa-kmr", "RAÄ Kulturmiljöregistret")


@pytest.mark.parametrize(
    ("scope", "identity"),
    [
        (DatasetScope.country("Sweden"), "country:sweden"),
        (DatasetScope.county("Östergötland"), "county:östergötland"),
        (DatasetScope.municipality("Vaxholm"), "municipality:vaxholm"),
        (DatasetScope.bbox(BoundingBox(14, 57, 17, 59)), "bbox:14,57,17,59"),
    ],
)
def test_dataset_scope_has_deterministic_identity(
    scope: DatasetScope, identity: str
) -> None:
    assert scope.identity == identity


def test_dataset_instance_combines_source_and_scope_identity() -> None:
    instance = DatasetInstance.create(SOURCE, DatasetScope.municipality("Vaxholm"))

    assert instance.dataset_id == "raa-kmr:municipality:vaxholm"
    assert instance.source is SOURCE


def test_scope_rejects_missing_or_conflicting_values() -> None:
    with pytest.raises(ValueError, match="kräver"):
        DatasetScope.country(" ")
    with pytest.raises(ValueError, match="bounds"):
        DatasetScope.bbox(None)  # type: ignore[arg-type]
