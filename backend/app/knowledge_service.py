"""Atomic ingestion and bounded workspace-first semantic retrieval."""
import hashlib
import json
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .intelligence import IntelligenceError
from .knowledge_config import KnowledgeSettings
from .knowledge_models import KnowledgeDocument, KnowledgeChunk
from .knowledge_processing import extract_pages, split_chunks
from . import knowledge_provider as provider


def document_view(document: KnowledgeDocument) -> dict:
    return {field: getattr(document, field) for field in (
        'id', 'name', 'file_type', 'size_bytes', 'status', 'error_code',
        'chunk_count', 'created_at', 'updated_at',
    )}


def lock_workspace(session: Session, workspace: str):
    if session.bind.dialect.name == 'postgresql':
        lock_id = int.from_bytes(hashlib.sha256(workspace.encode()).digest()[:8], 'big', signed=True)
        session.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': lock_id})


def ingest(content: bytes, name: str, file_type: str, workspace: str,
           session: Session, config: KnowledgeSettings) -> dict:
    profile = provider.embedding_profile()
    checksum = hashlib.sha256(content).hexdigest()
    indexing = {'embedding': profile, 'size': config.chunk_size,
                'overlap': config.chunk_overlap, 'extraction_version': '1'}
    fingerprint = hashlib.sha256((checksum + json.dumps(indexing, sort_keys=True)).encode()).hexdigest()
    existing = session.scalar(select(KnowledgeDocument).where(
        KnowledgeDocument.workspace_id == workspace, KnowledgeDocument.fingerprint == fingerprint))
    if existing:
        if existing.status == 'ready':
            return {'document': document_view(existing), 'duplicate': True}
        # A crashed process leaves processing metadata. A re-upload may claim an
        # expired 15-minute lease. Final writes also check lease ownership below.
        lease = datetime.now(timezone.utc)
        claimed = session.execute(update(KnowledgeDocument).where(
            KnowledgeDocument.id == existing.id,
            (KnowledgeDocument.status == 'failed') | (KnowledgeDocument.updated_at < lease - timedelta(minutes=15)),
        ).values(status='processing', error_code=None, updated_at=lease).execution_options(synchronize_session=False))
        session.commit()
        if not claimed.rowcount:
            session.refresh(existing)
            return {'document': document_view(existing), 'duplicate': True}
        document = existing
        session.refresh(document)
    else:
        lock_workspace(session, workspace)
        # Another request may have created this version while we waited.
        concurrent = session.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.workspace_id == workspace, KnowledgeDocument.fingerprint == fingerprint))
        if concurrent:
            session.commit()
            return {'document': document_view(concurrent), 'duplicate': True}
        count = session.scalar(select(func.count()).select_from(KnowledgeDocument).where(
            KnowledgeDocument.workspace_id == workspace)) or 0
        if count >= config.workspace_documents:
            session.rollback()
            raise IntelligenceError('workspace_document_limit', 409)
        document = KnowledgeDocument(
            id=str(uuid4()), workspace_id=workspace, name=name, file_type=file_type,
            size_bytes=len(content), checksum=checksum, fingerprint=fingerprint,
            status='processing', chunk_count=0, source_metadata=indexing,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(document)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            document = session.scalar(select(KnowledgeDocument).where(
                KnowledgeDocument.workspace_id == workspace, KnowledgeDocument.fingerprint == fingerprint))
            if document is None:
                raise
            return {'document': document_view(document), 'duplicate': True}
    # Timestamp is the lease token. Save it outside the ORM identity map.
    document_id, lease_token = document.id, document.updated_at
    try:
        chunks = split_chunks(extract_pages(content, file_type), config.chunk_size, config.chunk_overlap)
        vectors = provider.embed([chunk['passage'] for chunk in chunks], profile)
        # Serialize final capacity checks in PostgreSQL for concurrent uploads.
        lock_workspace(session, workspace)
        current = session.scalar(select(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id).with_for_update().execution_options(populate_existing=True))
        if current.updated_at != lease_token or current.status != 'processing':
            session.rollback()
            raise IntelligenceError('processing_lease_changed', 409)
        count = session.scalar(select(func.count()).select_from(KnowledgeChunk).join(KnowledgeDocument).where(
            KnowledgeDocument.workspace_id == workspace)) or 0
        if count + len(chunks) > config.workspace_chunks:
            raise IntelligenceError('workspace_chunk_limit', 409)
        if len(vectors) != len(chunks):
            raise IntelligenceError('invalid_embedding_response', 502)
        session.add_all([KnowledgeChunk(id=str(uuid4()), document_id=document_id,
                        **chunk, embedding=vector) for chunk, vector in zip(chunks, vectors)])
        current.status, current.chunk_count = 'ready', len(chunks)
        current.source_metadata = {**indexing, 'dimensions': len(vectors[0])}
        current.updated_at = datetime.now(timezone.utc)
        session.commit()
        return {'document': document_view(current), 'duplicate': False}
    except IntelligenceError as exc:
        session.rollback()
        # Failed transactions never publish partial chunks. A stale worker may
        # not mark a newer worker's result as failed.
        session.execute(update(KnowledgeDocument).where(
            KnowledgeDocument.id == document_id, KnowledgeDocument.status == 'processing',
            KnowledgeDocument.updated_at == lease_token,
        ).values(status='failed', error_code=exc.code, updated_at=datetime.now(timezone.utc)))
        session.commit()
        raise


def retrieve(question: str, workspace: str, session: Session, config: KnowledgeSettings,
             top_k: int, document_ids: list[str] | None = None) -> list[dict]:
    statement = select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument).where(
        KnowledgeDocument.workspace_id == workspace, KnowledgeDocument.status == 'ready')
    if document_ids:
        statement = statement.where(KnowledgeDocument.id.in_(document_ids))
    rows = session.execute(statement.order_by(KnowledgeDocument.id, KnowledgeChunk.chunk_index)
                           .limit(config.workspace_chunks + 1)).all()
    if not rows:
        return []
    if len(rows) > config.workspace_chunks:
        raise IntelligenceError('workspace_chunk_limit', 409)
    profile = provider.embedding_profile()
    rows = [(chunk, doc) for chunk, doc in rows if doc.source_metadata['embedding'] == profile]
    if not rows:
        raise IntelligenceError('embedding_profile_changed_reupload_documents', 409)
    query_vector = provider.embed([question], profile)[0]
    scored = []
    for chunk, doc in rows:
        vector = provider.normalize(chunk.embedding)
        if len(vector) != len(query_vector):
            raise IntelligenceError('embedding_dimension_mismatch', 409)
        score = sum(a * b for a, b in zip(vector, query_vector))
        if score >= config.min_similarity:
            scored.append({'chunk_id': chunk.id, 'document_id': doc.id, 'name': doc.name,
                           'page_number': chunk.page_number, 'chunk_index': chunk.chunk_index,
                           'passage': chunk.passage, 'similarity': round(score, 6)})
    return sorted(scored, key=lambda source: (-source['similarity'], source['chunk_id']))[:top_k]


INSUFFICIENT = 'The available documents do not provide enough information to answer this question.'


def answer(question: str, sources: list[dict]) -> dict:
    if not sources:
        return {'status': 'insufficient_evidence', 'message': INSUFFICIENT, 'claims': [], 'sources': []}
    output, metadata = provider.explain(question, sources)
    if not output.sufficient:
        return {'status': 'insufficient_evidence', 'message': INSUFFICIENT,
                'claims': [], 'sources': [], 'model_metadata': metadata}
    retrieved = {source['chunk_id']: source for source in sources}
    citations, claims = [], []
    for claim in output.claims:
        source = retrieved.get(claim.source_id)
        if source is None or claim.quote not in source['passage']:
            raise IntelligenceError('invalid_citation', 502)
        citation_id = str(len(citations) + 1)
        citations.append({**source, 'passage': claim.quote, 'citation_id': citation_id})
        claims.append({'explanation': claim.explanation, 'citation_id': citation_id})
    return {'status': 'answered', 'message': 'AI-generated explanation — verify against the quoted evidence.',
            'claims': claims, 'sources': citations, 'model_metadata': metadata}
