import { readMeta } from "../../../lib/data";

export const dynamic = "force-dynamic";

/**
 * Vercel cron hits this daily. It does not call football-data.org.
 * Ratings are rebuilt by the GitHub Action, which commits data/artifacts
 * and lets the next deploy pick them up.
 */
export function GET(request: Request) {
  const secret = process.env.CRON_SECRET;
  if (secret) {
    const header = request.headers.get("authorization");
    if (header !== `Bearer ${secret}`) {
      return Response.json({ ok: false }, { status: 401 });
    }
  }
  const meta = readMeta();
  return Response.json({
    ok: true,
    generated_at: meta?.generated_at ?? null,
    matches_played: meta?.matches_played ?? null,
    upcoming: meta?.upcoming ?? null,
    message: "Serving precomputed artifacts. Refresh is the GitHub Action, not a live API call.",
  });
}
