"""Search Meta Threads by keyword and save the posts to CSV, most liked first.

    python threads_search.py "web scraping" "n8n" --max 100 --out threads.csv
    python threads_search.py --profiles mosseri zuck --out profiles.csv
"""
import argparse
import csv
import os
from pathlib import Path
import tempfile
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

    rows = list(client.dataset(run.default_dataset_id).iterate_items())
    return export_results(rows, args.keywords, args.profiles, args.out)


def export_results(rows, keywords, requested_profiles, output):
    """Export completed downloads, including headers for requested empty modes."""
    posts, profiles, problems = [], [], []
    for item in rows:
        {"post": posts, "profile": profiles}.get(item.get("type"), problems).append(item)
    posts.sort(key=lambda p: p.get("likes") or 0, reverse=True)
    export_posts = bool(keywords or posts)
    export_profiles = bool(requested_profiles or profiles)
    output = Path(output)
    if export_posts:
        write_csv(output, POST_COLUMNS, posts)
        print(f"{len(posts)} posts saved to {output}")
    if export_profiles:
        profile_output = output.with_name(output.stem + "-profiles.csv") if export_posts else output
        profile_rows = [{**profile, "bioLinks": " ".join(profile.get("bioLinks") or [])}
                        for profile in profiles]
        write_csv(profile_output, PROFILE_COLUMNS, profile_rows)
        print(f"{len(profiles)} profiles saved to {profile_output}")
    for problem in problems:
        print(f"no result for {problem.get('input') or problem.get('searchQuery') or problem.get('username')}: {problem.get('error')}", file=sys.stderr)
    if problems:
        print("Export contains input errors or unrecognized rows; inspect the messages above. Empty files are not a confirmed no-match result.", file=sys.stderr)
        return 2
    if not posts and not profiles:
        print("No posts or profiles returned; requested CSVs contain headers only.")
    return 0


def write_csv(path, columns, rows):
    # Replace each file only after it has been fully written. Mixed exports are not one transaction.
    path = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == "__main__":
    sys.exit(main())
