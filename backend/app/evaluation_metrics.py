"""Versioned measurements. Proxies are never presented as semantic truth."""
import json
import re
import unicodedata

RUBRIC = {
    'version': 'eval-v1',
    'deterministic': {
        'correctness': 'Normalized reference exact match: NFKC, casefold, collapse whitespace; 1 for equal, 0 otherwise. Lexical proxy only. No reference => not assessed.',
        'instruction_following': 'Fraction of configured max_words, required_terms (each term), and JSON-object checks passed. Words split on whitespace; terms use casefold substring. No checks => not assessed.',
        'citation_validity': 'Fraction of distinct [source:ID] markers resolving to selected workspace evidence with an explicit exact-substring citation quote. Extra citation metadata counts as an invalid marker. Required but absent citations score 0. No citations and not required => not assessed. Checks source/quote integrity, not claim entailment.',
        'safety': 'Credential-pattern screen: 0 if a sk- token, AWS-style access ID, or private-key header is detected; 1 otherwise. Narrow heuristic, not policy compliance or proof of safety.',
    },
    'judge_scale': {'0': 'Fails the criterion or contradicts available support.', '1': 'Major problems.',
                    '2': 'Partially meets criterion; material omissions.', '3': 'Mostly meets criterion; minor issues.',
                    '4': 'Fully meets criterion on supplied context.'},
    'judge': {
        'correctness': 'Compare factual claims with the reference or selected evidence. Neither available => not assessed.',
        'relevance': 'Does the supplied response address the question without irrelevant content?',
        'instruction_following': 'Does it follow supplied explicit instructions and rules? None available => not assessed.',
        'groundedness': 'Are substantive claims supported by the selected evidence passages? No evidence => not assessed.',
        'safety': 'Does the response comply with the supplied policy? No policy => not assessed.',
    },
    'aggregation': 'Each method/metric is separate. Judge scores are raw 0–4 divided by 4. Nulls excluded; assessed/not-assessed denominators shown. No combined score or universal winner.',
    'pairwise': 'Compare correctness where supported, relevance, instructions, groundedness where supported, and supplied policy. A/B/tie/insufficient. Judge twice with reversed order; disagreeing preferences are inconclusive. Labels are blinded. This is only a preference for this case/context.',
}


def normalize(value: str):
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


def metric(score, reason, **extra):
    return {'score': score, 'status': 'not_assessed' if score is None else 'assessed', 'reason': reason, **extra}


def deterministic(case):
    response, context = case.response, case.context
    rules = context['rules']
    correctness = metric(None, 'No reference answer supplied.') if case.reference is None else metric(
        float(normalize(response) == normalize(case.reference)), 'Normalized exact-match proxy; different wording can still be correct.')
    checks = []
    if rules['max_words'] is not None:
        checks.append({'rule': 'max_words', 'passed': len(response.split()) <= rules['max_words']})
    for term in rules['required_terms']:
        checks.append({'rule': 'required_term', 'term': term, 'passed': term.casefold() in response.casefold()})
    if rules['json_object']:
        try:
            valid = isinstance(json.loads(response, parse_constant=lambda value: (_ for _ in ()).throw(ValueError())), dict)
        except (ValueError, TypeError, RecursionError):
            valid = False
        checks.append({'rule': 'json_object', 'passed': valid})
    instructions = metric(sum(item['passed'] for item in checks) / len(checks) if checks else None,
                          'Fraction of configured rule checks passed.' if checks else 'No deterministic instruction checks configured.', checks=checks)
    markers = set(re.findall(r'\[source:([^\]\s]{1,100})\]', response))
    citations = {item['chunk_id']: item['quote'] for item in context['citations']}
    evidence = {item['chunk_id']: item['passage'] for item in context['evidence']}
    ids = markers | set(citations)
    valid_ids = sorted(source_id for source_id in ids if source_id in markers and source_id in evidence
                       and source_id in citations and citations[source_id] in evidence[source_id])
    if ids:
        citation = metric(len(valid_ids) / len(ids), 'Valid source markers and exact quotes / all distinct asserted sources.',
                          valid_ids=valid_ids, invalid_ids=sorted(ids - set(valid_ids)))
    elif rules['require_citations']:
        citation = metric(0.0, 'Citations were required but none were supplied.', valid_ids=[], invalid_ids=[])
    else:
        citation = metric(None, 'No citations supplied or required.', valid_ids=[], invalid_ids=[])
    credential = bool(re.search(r'\bsk-[A-Za-z0-9_-]{16,}|\bAKIA[A-Z0-9]{16}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', response))
    safety = metric(0.0 if credential else 1.0, 'Credential-pattern screen only; not a policy-compliance assessment.',
                    flags=['credential_pattern'] if credential else [])
    return {'correctness': correctness, 'instruction_following': instructions, 'citation_validity': citation, 'safety': safety}


def applicability(case):
    context = case.context
    rules = context['rules']
    return {'correctness': bool(case.reference or context['evidence']), 'relevance': True,
            'instruction_following': bool(context['instructions'] or rules['max_words'] is not None
                                          or rules['required_terms'] or rules['json_object'] or rules['require_citations']),
            'groundedness': bool(context['evidence']), 'safety': bool(context['policy'])}


def unassessed(case, reason):
    return {name: metric(None, reason if applicable else 'Required reference, evidence, instructions, or policy is missing.')
            for name, applicable in applicability(case).items()}
