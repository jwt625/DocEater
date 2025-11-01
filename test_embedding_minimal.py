#!/usr/bin/env python3
"""
Minimal test of PGVector + Jina CLIP v2 embedding integration for DocEater.

This script demonstrates:
1. Loading the Jina CLIP v2 model for multimodal embeddings
2. Creating embeddings for text and images
3. Storing embeddings in PostgreSQL with PGVector
4. Performing similarity search

Requirements:
- PostgreSQL with pgvector extension enabled
- Jina CLIP v2 model (will be downloaded automatically)
"""

import asyncio
import os

import asyncpg
from pgvector.asyncpg import register_vector
from PIL import Image
from sentence_transformers import SentenceTransformer

# Database configuration
DATABASE_URL = os.getenv(
    "DOCEATER_DATABASE_URL", "postgresql://localhost:5432/doceater"
)


class MinimalEmbeddingTest:
    """Minimal test class for PGVector + Jina CLIP v2 integration."""

    def __init__(self):
        self.model = None
        self.conn = None

    async def setup(self):
        """Initialize model and database connection."""
        print("🔄 Loading Jina CLIP v2 model...")
        # Load the Jina CLIP v2 model for multimodal embeddings
        self.model = SentenceTransformer("jinaai/jina-clip-v2", trust_remote_code=True)

        # Get embedding dimension by testing with a sample text
        test_embedding = self.model.encode(["test"], normalize_embeddings=True)
        self.embedding_dim = test_embedding.shape[1]
        print(f"✅ Model loaded. Embedding dimension: {self.embedding_dim}")

        # Connect to database
        print("🔄 Connecting to database...")
        self.conn = await asyncpg.connect(DATABASE_URL)

        # Enable pgvector extension
        await self.conn.execute("CREATE EXTENSION IF NOT EXISTS vector")

        # Register vector type with asyncpg
        await register_vector(self.conn)
        print("✅ PGVector extension enabled")

        # Create test table
        await self.create_test_table()

    async def create_test_table(self):
        """Create a test table for embeddings."""
        embedding_dim = self.embedding_dim

        await self.conn.execute("""
            DROP TABLE IF EXISTS test_embeddings
        """)

        await self.conn.execute(f"""
            CREATE TABLE test_embeddings (
                id SERIAL PRIMARY KEY,
                content_type TEXT NOT NULL,  -- 'text' or 'image'
                content TEXT NOT NULL,       -- text content or image description
                embedding vector({embedding_dim}) NOT NULL,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # Create index for vector similarity search
        await self.conn.execute("""
            CREATE INDEX ON test_embeddings
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)

        print("✅ Test table created with vector index")

    async def test_text_embeddings(self):
        """Test text embedding generation and storage."""
        print("\n📝 Testing text embeddings...")

        # Sample text content
        texts = [
            "Machine learning algorithms for document processing",
            "Computer vision techniques for image analysis",
            "Natural language processing and text understanding",
            "Deep learning models for multimodal AI systems",
            "Vector databases and similarity search methods",
        ]

        # Generate embeddings
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        print(f"✅ Generated {len(embeddings)} text embeddings")

        # Store in database
        for text, embedding in zip(texts, embeddings, strict=False):
            await self.conn.execute(
                """
                INSERT INTO test_embeddings (content_type, content, embedding)
                VALUES ($1, $2, $3)
            """,
                "text",
                text,
                embedding.tolist(),
            )

        print("✅ Text embeddings stored in database")
        return len(texts)

    async def test_image_embeddings(self):
        """Test image embedding generation and storage."""
        print("\n🖼️  Testing image embeddings...")

        # Create sample images (simple colored squares)
        image_descriptions = [
            ("Red square", (255, 0, 0)),
            ("Blue circle", (0, 0, 255)),
            ("Green triangle", (0, 255, 0)),
            ("Yellow star", (255, 255, 0)),
        ]

        images = []
        descriptions = []

        for desc, color in image_descriptions:
            # Create a simple 64x64 colored image
            img = Image.new("RGB", (64, 64), color)
            images.append(img)
            descriptions.append(desc)

        # Generate embeddings for images
        embeddings = self.model.encode(images, normalize_embeddings=True)
        print(f"✅ Generated {len(embeddings)} image embeddings")

        # Store in database
        for desc, embedding in zip(descriptions, embeddings, strict=False):
            await self.conn.execute(
                """
                INSERT INTO test_embeddings (content_type, content, embedding)
                VALUES ($1, $2, $3)
            """,
                "image",
                desc,
                embedding.tolist(),
            )

        print("✅ Image embeddings stored in database")
        return len(images)

    async def test_similarity_search(self):
        """Test vector similarity search."""
        print("\n🔍 Testing similarity search...")

        # Test query
        query = "machine learning and AI algorithms"
        query_embedding = self.model.encode([query], normalize_embeddings=True)[0]

        # Perform similarity search
        results = await self.conn.fetch(
            """
            SELECT
                content_type,
                content,
                1 - (embedding <=> $1) as similarity_score
            FROM test_embeddings
            ORDER BY embedding <=> $1
            LIMIT 5
        """,
            query_embedding.tolist(),
        )

        print(f"🔍 Query: '{query}'")
        print("📊 Top 5 similar results:")
        for i, row in enumerate(results, 1):
            print(
                f"  {i}. [{row['content_type']}] {row['content'][:60]}... "
                f"(similarity: {row['similarity_score']:.3f})"
            )

        return results

    async def test_cross_modal_search(self):
        """Test cross-modal search (text query finding images)."""
        print("\n🔄 Testing cross-modal search...")

        # Text query that should match image content
        query = "colorful geometric shapes and visual elements"
        query_embedding = self.model.encode([query], normalize_embeddings=True)[0]

        # Search specifically for images
        results = await self.conn.fetch(
            """
            SELECT
                content_type,
                content,
                1 - (embedding <=> $1) as similarity_score
            FROM test_embeddings
            WHERE content_type = 'image'
            ORDER BY embedding <=> $1
            LIMIT 3
        """,
            query_embedding.tolist(),
        )

        print(f"🔍 Text query: '{query}'")
        print("🖼️  Matching images:")
        for i, row in enumerate(results, 1):
            print(
                f"  {i}. {row['content']} (similarity: {row['similarity_score']:.3f})"
            )

        return results

    async def cleanup(self):
        """Clean up resources."""
        if self.conn:
            await self.conn.execute("DROP TABLE IF EXISTS test_embeddings")
            await self.conn.close()
            print("✅ Cleanup completed")

    async def run_full_test(self):
        """Run the complete test suite."""
        try:
            await self.setup()

            # Test embeddings
            text_count = await self.test_text_embeddings()
            image_count = await self.test_image_embeddings()

            # Test search
            await self.test_similarity_search()
            await self.test_cross_modal_search()

            # Summary
            print("\n✅ Test completed successfully!")
            print(f"   📝 Text embeddings: {text_count}")
            print(f"   🖼️  Image embeddings: {image_count}")
            print("   🔍 Similarity search: Working")
            print("   🔄 Cross-modal search: Working")

        except Exception as e:
            print(f"❌ Test failed: {e}")
            raise
        finally:
            await self.cleanup()


async def main():
    """Main test function."""
    print("🚀 Starting minimal PGVector + Jina CLIP v2 embedding test")
    print("=" * 60)

    test = MinimalEmbeddingTest()
    await test.run_full_test()

    print("\n" + "=" * 60)
    print("🎉 All tests passed! PGVector + Jina CLIP v2 integration is working.")


if __name__ == "__main__":
    asyncio.run(main())
