import pytest
from app.ingestion import CSVError, validate_csv

HEADER = 'complaint_id,title,category,status,priority,channel,received_date\n'


def test_valid_csv_returns_typed_record_and_invalid_row_errors():
    content = (HEADER + 'CMP_1,Refund delayed,Refund delay,OPEN,HIGH,Email,2026-10-18\n'
               'bad id,Broken,Returns,unknown,urgent,Web,18-10-2026\n').encode()
    records, invalid, errors = validate_csv(content)
    assert records[0]['received_date'].isoformat() == '2026-10-18'
    assert records[0]['status'] == 'open'
    assert invalid == 1
    assert errors[0]['row'] == 3


@pytest.mark.parametrize('content, message', [
    (b'wrong\nvalue\n', 'exactly these unique'),
    (HEADER.encode(), 'no data rows'),
    (b'\xff\xfe', 'UTF-8'),
])
def test_invalid_file_level_csv_is_rejected(content, message):
    with pytest.raises(CSVError, match=message):
        validate_csv(content)


def test_invalid_data_row_is_reported_without_rejecting_valid_rows():
    records, invalid, errors = validate_csv(HEADER.encode() + b'C,a,c,open,low,x,not-a-date\n')
    assert records == []
    assert invalid == 1
    assert errors[0]['row'] == 2
