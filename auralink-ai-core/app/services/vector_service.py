"""
Vector Service - pgvector Integration
Enterprise-grade vector similarity search with fallback to pure Python
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import numpy as np

import asyncpg

logger = logging.getLogger(__name__)


class VectorService:
    """
    Vector Similarity Service with pgvector support
    
    Features:
    - pgvector extension integration (if available)
    - Pure Python cosine similarity fallback
    - Efficient batch operations
    - Hybrid search (vector + keyword)
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.has_pgvector = False
        self.embedding_dimension = 1536  # OpenAI ada-002
    
    async def initialize(self):
        """Check if pgvector extension is available"""
        try:
            async with self.db_pool.acquire() as conn:
                # Try to enable pgvector extension
                await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
                
                # Check if it's available
                result = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM pg_extension WHERE extname = 'vector'
                    )
                    """
                )
                
                if result:
                    self.has_pgvector = True
                    logger.info("✓ pgvector extension enabled")
                    
                    # Try to add embedding column if it doesn't exist
                    await self._add_embedding_column(conn)
                else:
                    logger.warning("⚠️  pgvector extension not available, using fallback similarity")
        
        except Exception as e:
            logger.warning(f"⚠️  Could not initialize pgvector: {e}")
            logger.info("Using Python-based similarity search as fallback")
    
    async def _add_embedding_column(self, conn: asyncpg.Connection):
        """Add embedding column to memory_chunks if it doesn't exist"""
        try:
            # Check if column exists
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'memory_chunks' AND column_name = 'embedding'
                )
                """
            )
            
            if not exists:
                # Add embedding column
                await conn.execute(
                    f"ALTER TABLE memory_chunks ADD COLUMN embedding vector({self.embedding_dimension})"
                )
                
                # Create index for similarity search
                await conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memory_chunks_embedding 
                    ON memory_chunks USING ivfflat (embedding vector_cosine_ops)
                    """
                )
                
                logger.info("✓ Added embedding column and index to memory_chunks")
        
        except Exception as e:
            logger.warning(f"Could not add embedding column: {e}")
    
    async def store_embedding(
        self,
        chunk_id: UUID,
        embedding: List[float]
    ) -> bool:
        """
        Store embedding vector for a memory chunk
        """
        if not self.has_pgvector:
            # Store in metadata instead
            return await self._store_embedding_fallback(chunk_id, embedding)
        
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE memory_chunks
                    SET embedding = $1::vector
                    WHERE chunk_id = $2
                    """,
                    embedding,
                    chunk_id
                )
            
            return True
        
        except Exception as e:
            logger.error(f"Error storing embedding: {e}")
            return False
    
    async def _store_embedding_fallback(
        self,
        chunk_id: UUID,
        embedding: List[float]
    ) -> bool:
        """Store embedding in JSONB metadata when pgvector is not available"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE memory_chunks
                    SET embedding_metadata = jsonb_set(
                        embedding_metadata,
                        '{vector}',
                        $1::jsonb
                    )
                    WHERE chunk_id = $2
                    """,
                    embedding,
                    chunk_id
                )
            
            return True
        
        except Exception as e:
            logger.error(f"Error storing embedding fallback: {e}")
            return False
    
    async def vector_search(
        self,
        query_embedding: List[float],
        user_id: UUID,
        agent_id: Optional[UUID] = None,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for similar vectors
        
        Returns chunks ordered by similarity (highest first)
        """
        if self.has_pgvector:
            return await self._vector_search_pgvector(
                query_embedding, user_id, agent_id, limit, threshold
            )
        else:
            return await self._vector_search_fallback(
                query_embedding, user_id, agent_id, limit, threshold
            )
    
    async def _vector_search_pgvector(
        self,
        query_embedding: List[float],
        user_id: UUID,
        agent_id: Optional[UUID],
        limit: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """Vector search using pgvector extension"""
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        chunk_id, content, source_type, source_id,
                        context, metadata, created_at,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM memory_chunks
                    WHERE user_id = $2
                        AND ($3::UUID IS NULL OR agent_id = $3)
                        AND embedding IS NOT NULL
                        AND (expires_at IS NULL OR expires_at > NOW())
                        AND 1 - (embedding <=> $1::vector) >= $4
                    ORDER BY embedding <=> $1::vector
                    LIMIT $5
                    """,
                    query_embedding,
                    user_id,
                    agent_id,
                    threshold,
                    limit
                )
            
            return [dict(row) for row in rows]
        
        except Exception as e:
            logger.error(f"pgvector search error: {e}")
            # Fallback to Python implementation
            return await self._vector_search_fallback(
                query_embedding, user_id, agent_id, limit, threshold
            )
    
    async def _vector_search_fallback(
        self,
        query_embedding: List[float],
        user_id: UUID,
        agent_id: Optional[UUID],
        limit: int,
        threshold: float
    ) -> List[Dict[str, Any]]:
        """Vector search using pure Python (fallback)"""
        try:
            # Fetch all chunks with embeddings in metadata
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    """
                    SELECT 
                        chunk_id, content, source_type, source_id,
                        context, metadata, created_at,
                        embedding_metadata
                    FROM memory_chunks
                    WHERE user_id = $1
                        AND ($2::UUID IS NULL OR agent_id = $2)
                        AND embedding_metadata ? 'vector'
                        AND (expires_at IS NULL OR expires_at > NOW())
                    """,
                    user_id,
                    agent_id
                )
            
            # Calculate similarities in Python
            query_vec = np.array(query_embedding)
            results = []
            
            for row in rows:
                try:
                    # Extract embedding from metadata
                    embedding_data = row['embedding_metadata'].get('vector')
                    if not embedding_data:
                        continue
                    
                    chunk_vec = np.array(embedding_data)
                    
                    # Cosine similarity
                    similarity = self._cosine_similarity(query_vec, chunk_vec)
                    
                    if similarity >= threshold:
                        result = dict(row)
                        result['similarity'] = float(similarity)
                        results.append(result)
                
                except Exception as e:
                    logger.debug(f"Error calculating similarity: {e}")
                    continue
            
            # Sort by similarity (highest first) and limit
            results.sort(key=lambda x: x['similarity'], reverse=True)
            return results[:limit]
        
        except Exception as e:
            logger.error(f"Fallback vector search error: {e}")
            return []
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    async def hybrid_search(
        self,
        query_embedding: List[float],
        query_text: str,
        user_id: UUID,
        agent_id: Optional[UUID] = None,
        limit: int = 5,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search combining vector similarity and keyword search
        
        Args:
            vector_weight: Weight for vector similarity (0-1)
            keyword_weight: Weight for keyword search (0-1)
        """
        # Get vector search results
        vector_results = await self.vector_search(
            query_embedding, user_id, agent_id, limit * 2, threshold=0.5
        )
        
        # Get keyword search results
        keyword_results = await self._keyword_search(
            query_text, user_id, agent_id, limit * 2
        )
        
        # Combine results with weighted scoring
        combined_scores: Dict[UUID, Dict[str, Any]] = {}
        
        # Process vector results
        for i, result in enumerate(vector_results):
            chunk_id = result['chunk_id']
            vector_score = result.get('similarity', 0.0)
            combined_scores[chunk_id] = {
                **result,
                'vector_score': vector_score,
                'keyword_score': 0.0,
                'combined_score': vector_score * vector_weight
            }
        
        # Process keyword results
        for i, result in enumerate(keyword_results):
            chunk_id = result['chunk_id']
            keyword_score = result.get('score', 0.0)
            
            if chunk_id in combined_scores:
                combined_scores[chunk_id]['keyword_score'] = keyword_score
                combined_scores[chunk_id]['combined_score'] += keyword_score * keyword_weight
            else:
                combined_scores[chunk_id] = {
                    **result,
                    'vector_score': 0.0,
                    'keyword_score': keyword_score,
                    'combined_score': keyword_score * keyword_weight
                }
        
        # Sort by combined score
        results = list(combined_scores.values())
        results.sort(key=lambda x: x['combined_score'], reverse=True)
        
        return results[:limit]
    
    async def _keyword_search(
        self,
        query: str,
        user_id: UUID,
        agent_id: Optional[UUID],
        limit: int
    ) -> List[Dict[str, Any]]:
        """Keyword-based full-text search"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    chunk_id, content, source_type, source_id,
                    context, metadata, created_at,
                    ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) as score
                FROM memory_chunks
                WHERE user_id = $2
                    AND ($3::UUID IS NULL OR agent_id = $3)
                    AND (expires_at IS NULL OR expires_at > NOW())
                    AND to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                ORDER BY score DESC
                LIMIT $4
                """,
                query, user_id, agent_id, limit
            )
        
        return [dict(row) for row in rows]
    
    async def batch_store_embeddings(
        self,
        chunk_embeddings: List[Tuple[UUID, List[float]]]
    ) -> int:
        """
        Store multiple embeddings in batch
        
        Args:
            chunk_embeddings: List of (chunk_id, embedding) tuples
        
        Returns:
            Number of embeddings stored
        """
        if not chunk_embeddings:
            return 0
        
        stored_count = 0
        
        for chunk_id, embedding in chunk_embeddings:
            try:
                success = await self.store_embedding(chunk_id, embedding)
                if success:
                    stored_count += 1
            except Exception as e:
                logger.error(f"Error storing embedding for chunk {chunk_id}: {e}")
        
        return stored_count
    
    def get_status(self) -> Dict[str, Any]:
        """Get vector service status"""
        return {
            "pgvector_enabled": self.has_pgvector,
            "embedding_dimension": self.embedding_dimension,
            "search_method": "pgvector" if self.has_pgvector else "python_fallback"
        }


# Singleton instance
_vector_service: Optional[VectorService] = None


def get_vector_service(db_pool: asyncpg.Pool) -> VectorService:
    """Get Vector Service singleton"""
    global _vector_service
    
    if _vector_service is None:
        _vector_service = VectorService(db_pool)
    
    return _vector_service
