"""
Memory Service - SuperMemory.ai Architecture Implementation
Connect → Ingest → Embed → Index → Recall → Evolve Pipeline
"""

import asyncio
import hashlib
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import numpy as np
from openai import AsyncOpenAI

from app.services.vector_service import VectorService

logger = logging.getLogger(__name__)


class MemoryService:
    """
    Memory Service implementing SuperMemory.ai architecture
    
    Pipeline:
    1. Connect: Receive data from various sources
    2. Ingest: Clean and chunk data
    3. Embed: Generate vector embeddings
    4. Index: Store in vector + graph database
    5. Recall: Semantic + keyword search
    6. Evolve: Update, extend, derive, and expire memories
    """
    
    def __init__(self, db_pool: asyncpg.Pool, openai_client: AsyncOpenAI):
        self.db_pool = db_pool
        self.openai_client = openai_client
        self.embedding_model = "text-embedding-ada-002"
        self.embedding_dimension = 1536
        self.vector_service = VectorService(db_pool) if db_pool else None
        
    # ========================================================================
    # 1. CONNECT - Receive data
    # ========================================================================
    
    async def connect_data(
        self,
        content: str,
        user_id: UUID,
        source_type: str,
        source_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Connect step: Receive data from various sources
        """
        logger.info(f"Connecting data from {source_type} for user {user_id}")
        
        return {
            "content": content,
            "user_id": user_id,
            "source_type": source_type,
            "source_id": source_id,
            "context": context or {},
            "metadata": metadata or {},
            "agent_id": agent_id
        }
    
    # ========================================================================
    # 2. INGEST - Clean and chunk data
    # ========================================================================
    
    async def ingest_data(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Ingest step: Clean and chunk data
        """
        logger.info(f"Ingesting data for user {data['user_id']}")
        
        content = data["content"]
        
        # Clean content
        cleaned_content = self._clean_content(content)
        
        # Chunk content
        chunks = self._chunk_content(cleaned_content)
        
        # Create chunk objects
        chunk_objects = []
        for chunk_text in chunks:
            # Generate hash for deduplication
            content_hash = hashlib.sha256(chunk_text.encode()).hexdigest()
            
            chunk_objects.append({
                "content": chunk_text,
                "content_hash": content_hash,
                "user_id": data["user_id"],
                "agent_id": data.get("agent_id"),
                "source_type": data["source_type"],
                "source_id": data.get("source_id"),
                "context": data.get("context", {}),
                "metadata": data.get("metadata", {}),
            })
        
        logger.info(f"Ingested {len(chunk_objects)} chunks")
        return chunk_objects
    
    def _clean_content(self, content: str) -> str:
        """Clean and normalize content"""
        # Remove excessive whitespace
        content = " ".join(content.split())
        
        # Remove special characters that may interfere with embedding
        # Keep basic punctuation for context
        
        return content.strip()
    
    def _chunk_content(
        self,
        content: str,
        max_chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        Chunk content into smaller pieces with overlap
        """
        if len(content) <= max_chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            end = start + max_chunk_size
            
            # Try to break at sentence boundary
            if end < len(content):
                # Look for period, exclamation, or question mark
                sentence_end = max(
                    content.rfind(".", start, end),
                    content.rfind("!", start, end),
                    content.rfind("?", start, end)
                )
                
                if sentence_end > start:
                    end = sentence_end + 1
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks
    
    # ========================================================================
    # 3. EMBED - Generate embeddings
    # ========================================================================
    
    async def embed_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Embed step: Generate vector embeddings for chunks
        """
        logger.info(f"Embedding {len(chunks)} chunks")
        
        # Extract text content
        texts = [chunk["content"] for chunk in chunks]
        
        # Generate embeddings in batches
        embeddings = await self._generate_embeddings_batch(texts)
        
        # Add embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
            chunk["embedding_metadata"] = {
                "model": self.embedding_model,
                "dimension": self.embedding_dimension,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        return chunks
    
    async def _generate_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 100
    ) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts
        """
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            
            try:
                response = await self.openai_client.embeddings.create(
                    model=self.embedding_model,
                    input=batch
                )
                
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                
            except Exception as e:
                logger.error(f"Error generating embeddings: {e}")
                # Fallback: zero embeddings
                all_embeddings.extend([[0.0] * self.embedding_dimension] * len(batch))
        
        return all_embeddings
    
    # ========================================================================
    # 4. INDEX - Store in database
    # ========================================================================
    
    async def index_chunks(self, chunks: List[Dict[str, Any]]) -> List[UUID]:
        """
        Index step: Store chunks in database
        """
        logger.info(f"Indexing {len(chunks)} chunks")
        
        chunk_ids = []
        
        async with self.db_pool.acquire() as conn:
            for chunk in chunks:
                # Check for duplicate
                existing = await conn.fetchval(
                    """
                    SELECT chunk_id FROM memory_chunks
                    WHERE content_hash = $1 AND user_id = $2
                    """,
                    chunk["content_hash"],
                    chunk["user_id"]
                )
                
                if existing:
                    logger.debug(f"Chunk already exists: {existing}")
                    chunk_ids.append(existing)
                    continue
                
                # Insert new chunk
                chunk_id = await conn.fetchval(
                    """
                    INSERT INTO memory_chunks (
                        user_id, agent_id, content, content_hash,
                        embedding_metadata, source_type, source_id,
                        context, metadata
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                    RETURNING chunk_id
                    """,
                    chunk["user_id"],
                    chunk.get("agent_id"),
                    chunk["content"],
                    chunk["content_hash"],
                    chunk.get("embedding_metadata", {}),
                    chunk["source_type"],
                    chunk.get("source_id"),
                    chunk.get("context", {}),
                    chunk.get("metadata", {})
                )
                
                chunk_ids.append(chunk_id)
                
                # Store embedding using vector service (pgvector or fallback)
                if self.vector_service and "embedding" in chunk:
                    await self.vector_service.store_embedding(chunk_id, chunk["embedding"])
        
        # Auto-discover relationships
        await self._discover_relationships(chunk_ids)
        
        logger.info(f"Indexed {len(chunk_ids)} chunks")
        return chunk_ids
    
    async def _discover_relationships(self, chunk_ids: List[UUID]):
        """
        Automatically discover relationships between chunks using vector similarity
        """
        if not chunk_ids or not self.vector_service:
            return
        
        try:
            # Get embeddings for new chunks
            async with self.db_pool.acquire() as conn:
                for chunk_id in chunk_ids:
                    # Get chunk embedding
                    row = await conn.fetchrow(
                        "SELECT embedding_metadata FROM memory_chunks WHERE chunk_id = $1",
                        chunk_id
                    )
                    
                    if not row or not row['embedding_metadata'].get('vector'):
                        continue
                    
                    embedding = row['embedding_metadata']['vector']
                    
                    # Find similar chunks
                    similar = await self.vector_service.vector_search(
                        embedding, 
                        None,  # Will be filtered by user_id in query
                        None, 
                        limit=5, 
                        threshold=0.8
                    )
                    
                    # Create relationships
                    for similar_chunk in similar:
                        if similar_chunk['chunk_id'] != chunk_id:
                            await conn.execute(
                                """
                                INSERT INTO memory_relationships 
                                (user_id, source_chunk_id, target_chunk_id, relationship_type, strength)
                                SELECT user_id, $1, $2, 'relates_to', $3
                                FROM memory_chunks WHERE chunk_id = $1
                                ON CONFLICT (source_chunk_id, target_chunk_id, relationship_type) DO NOTHING
                                """,
                                chunk_id,
                                similar_chunk['chunk_id'],
                                similar_chunk.get('similarity', 0.8)
                            )
        
        except Exception as e:
            logger.error(f"Error discovering relationships: {e}")
    
    # ========================================================================
    # 5. RECALL - Search and retrieve
    # ========================================================================
    
    async def recall(
        self,
        query: str,
        user_id: UUID,
        agent_id: Optional[UUID] = None,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Recall step: Search memories using semantic + keyword search
        """
        start_time = datetime.utcnow()
        logger.info(f"Recalling memories for query: {query[:50]}...")
        
        # Generate query embedding
        query_embedding = await self._generate_embeddings_batch([query])
        query_vector = query_embedding[0]
        
        # Use vector service for semantic search if available
        if self.vector_service:
            results = await self.vector_service.hybrid_search(
                query_vector, query, user_id, agent_id, limit
            )
        else:
            # Fallback to keyword search only
            results = await self._keyword_search(
                query, user_id, agent_id, limit
            )
        
        # Enrich with graph context
        enriched_results = await self._enrich_with_context(results)
        
        # Track recall session
        recall_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        await self._track_recall_session(
            user_id, agent_id, query, len(enriched_results), recall_time_ms
        )
        
        logger.info(f"Recalled {len(enriched_results)} memories in {recall_time_ms}ms")
        return enriched_results
    
    async def _keyword_search(
        self,
        query: str,
        user_id: UUID,
        agent_id: Optional[UUID],
        limit: int
    ) -> List[Dict[str, Any]]:
        """
        Keyword-based full-text search
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    chunk_id, content, source_type, source_id,
                    context, metadata, created_at, accessed_at,
                    ts_rank(to_tsvector('english', content), plainto_tsquery('english', $1)) as score
                FROM memory_chunks
                WHERE user_id = $2
                    AND ($3::UUID IS NULL OR agent_id = $3)
                    AND (expires_at IS NULL OR expires_at > NOW())
                    AND to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                ORDER BY score DESC, created_at DESC
                LIMIT $4
                """,
                query, user_id, agent_id, limit
            )
        
        return [dict(row) for row in rows]
    
    async def _enrich_with_context(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich results with graph relationships
        """
        if not results:
            return results
        
        chunk_ids = [result["chunk_id"] for result in results]
        
        async with self.db_pool.acquire() as conn:
            # Get related chunks
            related_rows = await conn.fetch(
                """
                SELECT 
                    r.source_chunk_id,
                    r.target_chunk_id,
                    r.relationship_type,
                    r.strength,
                    c.content as related_content
                FROM memory_relationships r
                JOIN memory_chunks c ON c.chunk_id = r.target_chunk_id
                WHERE r.source_chunk_id = ANY($1::UUID[])
                ORDER BY r.strength DESC
                LIMIT 10
                """,
                chunk_ids
            )
        
        # Build relationships map
        relationships_map = {}
        for row in related_rows:
            source_id = row["source_chunk_id"]
            if source_id not in relationships_map:
                relationships_map[source_id] = []
            
            relationships_map[source_id].append({
                "type": row["relationship_type"],
                "strength": float(row["strength"]),
                "content": row["related_content"][:100]  # Preview
            })
        
        # Add relationships to results
        for result in results:
            result["related_memories"] = relationships_map.get(
                result["chunk_id"], []
            )
        
        return results
    
    async def _track_recall_session(
        self,
        user_id: UUID,
        agent_id: Optional[UUID],
        query: str,
        results_count: int,
        recall_time_ms: int
    ):
        """Track recall session for analytics"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO memory_sessions (
                    user_id, agent_id, query, results_count, recall_time_ms
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                user_id, agent_id, query, results_count, recall_time_ms
            )
    
    # ========================================================================
    # 6. EVOLVE - Update and maintain memories
    # ========================================================================
    
    async def evolve_memories(self, user_id: UUID) -> Dict[str, int]:
        """
        Evolve step: Update, extend, derive, and expire memories
        """
        logger.info(f"Evolving memories for user {user_id}")
        
        stats = {
            "updated": 0,
            "extended": 0,
            "derived": 0,
            "expired": 0
        }
        
        # 1. Update memories with new information
        stats["updated"] = await self._update_memories(user_id)
        
        # 2. Extend related memories
        stats["extended"] = await self._extend_memories(user_id)
        
        # 3. Derive new insights
        stats["derived"] = await self._derive_insights(user_id)
        
        # 4. Expire old memories
        stats["expired"] = await self._expire_old_memories(user_id)
        
        logger.info(f"Evolution complete: {stats}")
        return stats
    
    async def _update_memories(self, user_id: UUID) -> int:
        """Update memories with new information by merging similar chunks"""
        try:
            updated_count = 0
            
            # Find duplicate or highly similar chunks
            async with self.db_pool.acquire() as conn:
                # Find chunks with same content hash
                duplicates = await conn.fetch(
                    """
                    SELECT content_hash, array_agg(chunk_id) as chunk_ids
                    FROM memory_chunks
                    WHERE user_id = $1
                    GROUP BY content_hash
                    HAVING COUNT(*) > 1
                    """,
                    user_id
                )
                
                for dup in duplicates:
                    chunk_ids = dup['chunk_ids']
                    # Keep the newest, delete others
                    await conn.execute(
                        """
                        DELETE FROM memory_chunks
                        WHERE chunk_id = ANY($1::UUID[])
                        AND chunk_id != (
                            SELECT chunk_id FROM memory_chunks
                            WHERE chunk_id = ANY($1::UUID[])
                            ORDER BY created_at DESC LIMIT 1
                        )
                        """,
                        chunk_ids
                    )
                    updated_count += len(chunk_ids) - 1
            
            return updated_count
        
        except Exception as e:
            logger.error(f"Error updating memories: {e}")
            return 0
    
    async def _extend_memories(self, user_id: UUID) -> int:
        """Extend related memories by creating new relationships"""
        try:
            # Get recent chunks without many relationships
            async with self.db_pool.acquire() as conn:
                chunks = await conn.fetch(
                    """
                    SELECT c.chunk_id
                    FROM memory_chunks c
                    LEFT JOIN memory_relationships r ON c.chunk_id = r.source_chunk_id
                    WHERE c.user_id = $1
                        AND c.created_at > NOW() - INTERVAL '7 days'
                    GROUP BY c.chunk_id
                    HAVING COUNT(r.relationship_id) < 3
                    LIMIT 50
                    """,
                    user_id
                )
                
                # Discover relationships for these chunks
                chunk_ids = [row['chunk_id'] for row in chunks]
                await self._discover_relationships(chunk_ids)
                
                return len(chunk_ids)
        
        except Exception as e:
            logger.error(f"Error extending memories: {e}")
            return 0
    
    async def _derive_insights(self, user_id: UUID) -> int:
        """Derive new insights from existing memories using LLM analysis"""
        try:
            # Get recent memories
            async with self.db_pool.acquire() as conn:
                chunks = await conn.fetch(
                    """
                    SELECT content, context, metadata
                    FROM memory_chunks
                    WHERE user_id = $1
                        AND created_at > NOW() - INTERVAL '7 days'
                    ORDER BY created_at DESC
                    LIMIT 20
                    """,
                    user_id
                )
                
                if len(chunks) < 5:
                    return 0
                
                # Aggregate content
                contents = [chunk['content'] for chunk in chunks]
                combined_text = "\n".join(contents)
                
                # Use LLM to derive insights
                try:
                    response = await self.openai_client.chat.completions.create(
                        model="gpt-4-turbo-preview",
                        messages=[
                            {
                                "role": "system",
                                "content": "Analyze the following memories and extract 2-3 key insights or patterns. Be concise."
                            },
                            {
                                "role": "user",
                                "content": combined_text[:4000]  # Limit token usage
                            }
                        ],
                        max_tokens=300,
                        temperature=0.5
                    )
                    
                    insight = response.choices[0].message.content
                    
                    # Store as a new memory
                    if insight:
                        await self.store_memory(
                            content=f"Insight: {insight}",
                            user_id=user_id,
                            source_type="system",
                            source_id="memory_evolution",
                            metadata={"type": "derived_insight"},
                            ttl_days=90
                        )
                        return 1
                
                except Exception as e:
                    logger.error(f"Error deriving insight with LLM: {e}")
                
                return 0
        
        except Exception as e:
            logger.error(f"Error deriving insights: {e}")
            return 0
    
    async def _expire_old_memories(self, user_id: UUID) -> int:
        """Expire old or irrelevant memories"""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM memory_chunks
                WHERE user_id = $1
                    AND expires_at IS NOT NULL
                    AND expires_at < NOW()
                """,
                user_id
            )
            
            # Parse "DELETE N" response
            deleted_count = int(result.split()[-1]) if result else 0
            return deleted_count
    
    # ========================================================================
    # HIGH-LEVEL API
    # ========================================================================
    
    async def store_memory(
        self,
        content: str,
        user_id: UUID,
        source_type: str,
        source_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[UUID] = None,
        ttl_days: Optional[int] = None
    ) -> List[UUID]:
        """
        Complete pipeline: Store memory from content
        """
        # 1. Connect
        data = await self.connect_data(
            content, user_id, source_type, source_id,
            context, metadata, agent_id
        )
        
        # 2. Ingest
        chunks = await self.ingest_data(data)
        
        # 3. Embed
        embedded_chunks = await self.embed_chunks(chunks)
        
        # Add expiration if needed
        if ttl_days:
            expires_at = datetime.utcnow() + timedelta(days=ttl_days)
            for chunk in embedded_chunks:
                chunk["expires_at"] = expires_at
        
        # 4. Index
        chunk_ids = await self.index_chunks(embedded_chunks)
        
        return chunk_ids
    
    async def delete_memory(self, chunk_id: UUID, user_id: UUID) -> bool:
        """Delete a memory (GDPR compliance)"""
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                DELETE FROM memory_chunks
                WHERE chunk_id = $1 AND user_id = $2
                """,
                chunk_id, user_id
            )
            
            return "DELETE 1" in result
    
    async def list_memories(
        self,
        user_id: UUID,
        agent_id: Optional[UUID] = None,
        skip: int = 0,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """List user's memories"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    chunk_id, content, source_type, source_id,
                    context, metadata, created_at, accessed_at
                FROM memory_chunks
                WHERE user_id = $1
                    AND ($2::UUID IS NULL OR agent_id = $2)
                    AND (expires_at IS NULL OR expires_at > NOW())
                ORDER BY created_at DESC
                OFFSET $3
                LIMIT $4
                """,
                user_id, agent_id, skip, limit
            )
        
        return [dict(row) for row in rows]
