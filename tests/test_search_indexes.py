"""Search index metadata tests."""
import src.models  # noqa: F401
from src.database import Base


def test_searchable_entities_have_composite_search_indexes():
    expected = {
        "events": "ix_events_search_title",
        "communities": "ix_communities_search_name",
        "profiles": "ix_profiles_search_identity",
        "tasks": "ix_tasks_search_title",
    }
    for table_name, index_name in expected.items():
        assert index_name in {index.name for index in Base.metadata.tables[table_name].indexes}
