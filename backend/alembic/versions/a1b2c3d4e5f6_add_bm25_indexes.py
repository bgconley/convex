"""add BM25 indexes for pg_search full-text search

Revision ID: a1b2c3d4e5f6
Revises: ddf7d4031241
Create Date: 2026-03-10

Creates BM25 indexes using ParadeDB pg_search on:
- chunks.chunk_text — for chunk-level keyword search
- documents.title + documents.rendered_markdown — for document-level search

These indexes enable the `|||` operator for BM25 full-text search
with `pdb.score()` for relevance scoring.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'ddf7d4031241'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # BM25 index on chunks.chunk_text with English stemmer
    # key_field='id' is required by pg_search
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_bm25_idx ON chunks "
        "USING bm25 (id, (chunk_text::pdb.simple('stemmer=english'))) "
        "WITH (key_field='id')"
    )

    # BM25 index on documents for document-level search
    # Indexes title and rendered_markdown with English stemmer
    op.execute(
        "CREATE INDEX IF NOT EXISTS documents_bm25_idx ON documents "
        "USING bm25 (id, "
        "(title::pdb.simple('stemmer=english')), "
        "(rendered_markdown::pdb.simple('stemmer=english'))) "
        "WITH (key_field='id')"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS documents_bm25_idx")
    op.execute("DROP INDEX IF EXISTS chunks_bm25_idx")
