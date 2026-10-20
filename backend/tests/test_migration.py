from pathlib import Path


def test_initial_migration_creates_complaint_constraints_and_indexes():
    source = (Path(__file__).parents[1] / 'migrations' / 'versions' / '0001_complaints.py').read_text()
    assert "op.create_table('complaints'" in source
    assert "ck_complaint_status" in source
    assert "ck_complaint_priority" in source
    assert "ix_complaints_received_date" in source
