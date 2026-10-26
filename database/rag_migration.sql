-- 1. Enable pgvector extension for similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create document_chunks table
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    material_id UUID NOT NULL REFERENCES materials(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding VECTOR(768),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    -- 4. Unique constraint on (material_id, chunk_index)
    UNIQUE(material_id, chunk_index)
);

-- 3. Create HNSW index for fast similarity search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON document_chunks 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- 4. Index on material_id for cascade deletes and fast lookups
CREATE INDEX IF NOT EXISTS idx_chunks_material_id ON document_chunks(material_id);

-- 5. Create the match_documents RPC function for RAG retrieval
CREATE OR REPLACE FUNCTION match_documents(
    query_embedding VECTOR(768),
    match_count INT DEFAULT 5,
    filter_material_ids UUID[] DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    material_id UUID,
    content TEXT,
    metadata JSONB,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.material_id,
        dc.content,
        dc.metadata,
        1 - (dc.embedding <=> query_embedding) AS similarity
    FROM document_chunks dc
    WHERE (filter_material_ids IS NULL 
           OR dc.material_id = ANY(filter_material_ids))
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- 6. Create conversation_history table for chat memory
CREATE TABLE IF NOT EXISTS conversation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    student_id UUID NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for retrieving a student's conversation history ordered by time
CREATE INDEX IF NOT EXISTS idx_conv_student_time 
    ON conversation_history(student_id, created_at DESC);

-- 7. Add an ingestion_status column to materials table to track which materials have been indexed
DO $$ 
BEGIN
    -- Only add check constraint if column doesn't exist, to keep it idempotent
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='materials' AND column_name='ingestion_status') THEN
        ALTER TABLE materials ADD COLUMN ingestion_status VARCHAR(20) DEFAULT 'pending' CHECK (ingestion_status IN ('pending', 'processing', 'completed', 'failed'));
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='materials' AND column_name='chunk_count') THEN
        ALTER TABLE materials ADD COLUMN chunk_count INTEGER DEFAULT 0;
    END IF;
END $$;

-- 8. Helper function to delete all chunks for a material (for re-indexing)
CREATE OR REPLACE FUNCTION delete_material_chunks(p_material_id UUID)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    DELETE FROM document_chunks WHERE material_id = p_material_id;
    UPDATE materials SET ingestion_status = 'pending', chunk_count = 0 WHERE id = p_material_id;
END;
$$;

-- 9. Function execution permissions (strictly restricted to authenticated and service_role, NO anon access)
REVOKE EXECUTE ON FUNCTION match_documents FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION match_documents TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION delete_material_chunks FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION delete_material_chunks TO authenticated, service_role;

-- 10. Enable Row Level Security (RLS)
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversation_history ENABLE ROW LEVEL SECURITY;

-- Revoke all direct permissions from anon
REVOKE ALL ON document_chunks FROM anon;
REVOKE ALL ON conversation_history FROM anon;

-- 11. RLS Policies
DROP POLICY IF EXISTS "Allow read access to document_chunks" ON document_chunks;
DROP POLICY IF EXISTS "Allow authenticated enrolled students to read document_chunks" ON document_chunks;
DROP POLICY IF EXISTS "Allow all to service_role on document_chunks" ON document_chunks;

-- Authenticated students can only read document chunks for courses/batches they are enrolled in
CREATE POLICY "Allow authenticated enrolled students to read document_chunks" ON document_chunks
    FOR SELECT TO authenticated
    USING (
        EXISTS (
            SELECT 1 FROM materials m
            LEFT JOIN student_batches sb ON sb.batch_id = m.batch_id
            LEFT JOIN student_courses sc ON sc.course_id = m.course_id
            WHERE m.id = document_chunks.material_id
              AND (sb.student_id = auth.uid() OR sc.student_id = auth.uid())
        )
        OR
        EXISTS (
            SELECT 1 FROM teachers t
            WHERE t.id = auth.uid()
        )
    );

-- Backend service role has full access for automated indexing, updates, and cascading deletes
CREATE POLICY "Allow all to service_role on document_chunks" ON document_chunks
    FOR ALL TO service_role USING (true) WITH CHECK (true);

-- Student conversation history: students can only access their own history
DROP POLICY IF EXISTS "Allow student conversation history access" ON conversation_history;
CREATE POLICY "Allow student conversation history access" ON conversation_history
    FOR ALL TO authenticated USING (auth.uid() = student_id) WITH CHECK (auth.uid() = student_id);

DROP POLICY IF EXISTS "Allow service_role full conversation history" ON conversation_history;
CREATE POLICY "Allow service_role full conversation history" ON conversation_history
    FOR ALL TO service_role USING (true) WITH CHECK (true);


