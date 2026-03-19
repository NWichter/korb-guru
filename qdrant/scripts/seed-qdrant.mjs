#!/usr/bin/env node
/**
 * Qdrant config + seed: collection definition and example vectors (single script, no separate migrations).
 * - Schema/config: collection name, vector size, distance (edit below).
 * - Seed: points array (vectors + payloads).
 * Run: pnpm db:seed:qdrant (or as part of pnpm db:reset).
 * Env: QDRANT_URL (default http://localhost:6333), optional QDRANT_API_KEY.
 */

const baseUrl = process.env.QDRANT_URL || 'http://localhost:6333';
const apiKey = process.env.QDRANT_API_KEY;
const collectionName = 'demo';

const headers = {
  'Content-Type': 'application/json',
  ...(apiKey && { 'api-key': apiKey }),
};

async function main() {
  try {
    const res = await fetch(`${baseUrl}/collections/${collectionName}`, {
      method: 'GET',
      headers,
    });
    if (res.ok) {
      await fetch(`${baseUrl}/collections/${collectionName}`, { method: 'DELETE', headers });
    }
  } catch {
    // ignore
  }

  const createRes = await fetch(`${baseUrl}/collections/${collectionName}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
      vectors: { size: 4, distance: 'Cosine' },
    }),
  });
  if (!createRes.ok) {
    const t = await createRes.text();
    throw new Error(`Create collection failed: ${createRes.status} ${t}`);
  }

  const pointsRes = await fetch(`${baseUrl}/collections/${collectionName}/points?wait=true`, {
    method: 'PUT',
    headers,
    body: JSON.stringify({
      points: [
        { id: 1, vector: [0.1, 0.2, 0.3, 0.4], payload: { name: 'First' } },
        { id: 2, vector: [0.2, 0.3, 0.4, 0.5], payload: { name: 'Second' } },
        { id: 3, vector: [0.3, 0.4, 0.5, 0.6], payload: { name: 'Third' } },
      ],
    }),
  });
  if (!pointsRes.ok) {
    const t = await pointsRes.text();
    throw new Error(`Upsert points failed: ${pointsRes.status} ${t}`);
  }

  console.log(`Qdrant seeded: collection "${collectionName}" with 3 example points at ${baseUrl}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
