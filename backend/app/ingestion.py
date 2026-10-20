"""Strict UTF-8 CSV validation, independent of HTTP and database code."""
import csv
import io
import re
from datetime import date

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 5000
MAX_ERRORS = 100
COLUMNS = {'complaint_id', 'title', 'category', 'status', 'priority', 'channel', 'received_date'}
LIMITS = {'complaint_id': 64, 'title': 300, 'category': 80, 'channel': 40}


class CSVError(ValueError):
    """A file-level error rejects the entire upload before any database write."""


def validate_csv(content: bytes):
    if not content or len(content) > MAX_BYTES:
        raise CSVError('CSV must be nonempty and at most 2 MiB.')
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        raise CSVError('CSV must be UTF-8 encoded.') from None
    if '\x00' in text:
        raise CSVError('CSV must not contain NUL bytes.')
    reader = csv.reader(io.StringIO(text, newline=''), strict=True)
    valid, errors, invalid = [], [], 0
    try:
        header = next(reader, [])
        if len(set(header)) != len(header) or set(header) != COLUMNS:
            raise CSVError('Use exactly these unique column names: ' + ', '.join(sorted(COLUMNS)))
        for number, values in enumerate(reader, start=2):
            if number - 1 > MAX_ROWS:
                raise CSVError('CSV exceeds the 5,000 row limit.')
            problems = []
            record = {}
            if len(values) != len(header):
                problems.append('Wrong number of columns.')
            else:
                record = {key: value.strip() for key, value in zip(header, values)}
                for key, limit in LIMITS.items():
                    if not record[key] or len(record[key]) > limit:
                        problems.append(f'{key} must contain 1–{limit} characters.')
                    if any(ord(char) < 32 for char in record[key]):
                        problems.append(f'{key} must not contain control characters.')
                if not re.fullmatch(r'[A-Za-z0-9_-]+', record['complaint_id']):
                    problems.append('complaint_id accepts letters, numbers, underscores and hyphens only.')
                for key, choices in [('status', {'open', 'in_progress', 'resolved'}), ('priority', {'low', 'medium', 'high'})]:
                    record[key] = record[key].lower()
                    if record[key] not in choices:
                        problems.append(f'{key} must be one of: ' + ', '.join(sorted(choices)))
                record['category'] = record['category'].lower()
                try:
                    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', record['received_date']):
                        raise ValueError()
                    record['received_date'] = date.fromisoformat(record['received_date'])
                except ValueError:
                    problems.append('received_date must be a valid YYYY-MM-DD date.')
            if problems:
                invalid += 1
                if len(errors) < MAX_ERRORS:
                    errors.append({'row': number, 'errors': problems})
            else:
                valid.append(record)
    except csv.Error:
        raise CSVError('Malformed CSV quoting or a field is too large.') from None
    if not valid and not invalid:
        raise CSVError('CSV has a header but no data rows.')
    return valid, invalid, errors
