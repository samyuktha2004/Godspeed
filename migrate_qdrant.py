"""Migrate local Qdrant collection to Qdrant Cloud. Run once before deploying."""
import asyncio, os, sys

COLLECTION = "knowledge_base"
CLOUD_URL = os.getenv("QDRANT_CLOUD_URL", "")
CLOUD_KEY = os.getenv("QDRANT_CLOUD_API_KEY", "")

if not CLOUD_URL or not CLOUD_KEY:
    print("Set QDRANT_CLOUD_URL and QDRANT_CLOUD_API_KEY env vars first")
    sys.exit(1)

async def migrate():
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.models import PointStruct

    src = AsyncQdrantClient(host="localhost", port=6333)
    dst = AsyncQdrantClient(url=CLOUD_URL, api_key=CLOUD_KEY)

    info = await src.get_collection(COLLECTION)
    print(f"Source collection: {info.points_count} points")

    try:
        await dst.delete_collection(COLLECTION)
    except Exception:
        pass

    # Create with both dense and sparse vector configs
    await dst.create_collection(
        COLLECTION,
        vectors_config=info.config.params.vectors,
        sparse_vectors_config=info.config.params.sparse_vectors,
    )
    print("Created cloud collection (dense + sparse)")

    offset = None
    total = 0
    while True:
        records, offset = await src.scroll(
            COLLECTION, offset=offset, limit=50,
            with_payload=True, with_vectors=True
        )
        if not records:
            break
        structs = [
            PointStruct(id=r.id, vector=r.vector, payload=r.payload or {})
            for r in records
            if r.vector is not None
        ]
        if structs:
            await dst.upsert(COLLECTION, points=structs)
        total += len(structs)
        print(f"Migrated {total} points...")
        if offset is None:
            break

    print(f"Done — {total} points migrated to {CLOUD_URL}")

asyncio.run(migrate())
