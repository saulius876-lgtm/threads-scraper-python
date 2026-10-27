"""Search Meta Threads by keyword and save the posts to CSV, most liked first.

    python threads_search.py "web scraping" "n8n" --max 100 --out threads.csv
    python threads_search.py --profiles mosseri zuck --out profiles.csv
"""
import argparse
import csv
import os
import sys

from apify_client import ApifyClient

ACTOR = "sauliusautomatesit/threads-search-api"
POST_COLUMNS = [
    "publishedAt", "username", "fullName", "isVerified", "likes", "replies", "reposts", "quotes", "shares",
    "mediaType", "text", "linkUrl", "url", "searchQuery",
]
PROFILE_COLUMNS = ["username", "fullName", "followers", "isVerified", "isPrivate", "biography", "bioLinks", "url"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("keywords", nargs="*", help="keywords or phrases: a brand, a product, a topic")
    parser.add_argument("--profiles", nargs="+", default=[], help="usernames for profile data (followers, bio, links)")
    parser.add_argument("--max", type=int, default=100, help="most posts per keyword (default 100)")
    parser.add_argument("--out", default="threads.csv")
    parser.add_argument("--max-spend", type=float, default=1.0, help="hard spending cap for the run in USD (default 1)")
    args = parser.parse_args()

    token = os.environ.get("APIFY_TOKEN")
    if not token:
        sys.exit("Set APIFY_TOKEN first (Apify Console > Settings > API & Integrations).")
    if not args.keywords and not args.profiles:
        sys.exit("Give at least one keyword or --profiles username.")

    run_input = {"searchQueries": args.keywords, "maxPostsPerQuery": args.max}
    if args.profiles:
        run_input["usernames"] = args.profiles
        run_input["maxPostsPerProfile"] = 0  # profile data only; set above 0 to add their latest threads

    client = ApifyClient(token)
    run = client.actor(ACTOR).call(run_input=run_input, max_total_charge_usd=args.max_spend, logger=None)
    if run is None or run.status != "SUCCEEDED":
        sys.exit(f"Run did not succeed: {run.status if run else 'not found'}")

    posts, profiles, problems = [], [], []
    for item in client.dataset(run.default_dataset_id).iterate_items():
        {"post": posts, "profile": profiles}.get(item.get("type"), problems).append(item)
    posts.sort(key=lambda p: p.get("likes") or 0, reverse=True)

    if posts:
        write_csv(args.out, POST_COLUMNS, posts)
        print(f"{len(posts)} posts saved to {args.out}")
    if profiles:
        out = args.out if not posts else args.out.replace(".csv", "") + "-profiles.csv"
        for p in profiles:
            p["bioLinks"] = " ".join(p.get("bioLinks") or [])
        write_csv(out, PROFILE_COLUMNS, profiles)
        print(f"{len(profiles)} profiles saved to {out}")
    for p in problems:
        print(f"no result for {p.get('input') or p.get('searchQuery') or p.get('username')}: {p.get('error')}")


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
