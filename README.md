# Threads scraper in Python: search Meta Threads posts by keyword to CSV

`threads_search.py` searches [Threads](https://www.threads.com) for any keyword and saves every
public post Threads shows for it, with author, likes, replies, reposts, quotes, shares, media type,
links and post date, sorted by likes. It can also look up profiles (followers, bio, links).

Use it for brand and competitor monitoring, trend research, finding who posts about your niche, or
feeding fresh posts to an LLM pipeline. No Threads or Instagram account, no cookies, no browser.

Meta's official Threads API needs a developer app and access tokens, and searching other people's
posts with it needs extra permissions from Meta. The script calls the [Threads Search Scraper API](https://apify.com/sauliusautomatesit/threads-search-api)
on Apify, which reads what Threads shows a logged-out visitor and returns plain JSON. Disclosure: I
build and maintain that Actor. It is pay per post (prices below), and every run has a spending cap.

## Setup

```bash
git clone https://github.com/saulius876-lgtm/threads-scraper-python
cd threads-scraper-python
pip install -r requirements.txt
export APIFY_TOKEN=your_token   # Windows PowerShell: $env:APIFY_TOKEN="your_token"
```

The token is in [Apify Console](https://console.apify.com/settings/integrations) under
Settings > API & Integrations. A free Apify account works.

## Search posts by keyword

```bash
python threads_search.py "web scraping" --max 20 --out threads.csv
```

```text
20 posts saved to threads.csv
```

Output from a real run on 27 Oct 2026 (two of the rows, text shortened):

| publishedAt | username | likes | replies | reposts | text |
|---|---|---:|---:|---:|---|
| 2026-08-30 | gitrepos_ | 125 | 2 | 18 | Scrapling ⭐ 77k  Scrapling is an open-source library that automatically ... |
| 2026-08-02 | githubprojects | 46 | 1 | 9 | 30-day Python curriculum that goes from variables and operators to ... |

Columns: `publishedAt`, `username`, `fullName`, `isVerified`, `likes`, `replies`, `reposts`,
`quotes`, `shares`, `mediaType`, `text`, `linkUrl`, `url`, `searchQuery`.

Several keywords in one run, 100 posts each:

```bash
python threads_search.py "your brand" "competitor one" "competitor two" --max 100
```

## Profiles

```bash
python threads_search.py --profiles mosseri --out profiles.csv
```

| username | fullName | followers | isVerified | biography | bioLinks |
|---|---|---:|---|---|---|
| mosseri | Adam Mosseri | 1052852 | True | Father of three boys, married to an amazing woman, head of Instagram and supporter of Threads. | http://mosseri.net/ |

With keywords and `--profiles` together, profiles go to a second file, `threads-profiles.csv`.

## Calling it from your own code

```python
from apify_client import ApifyClient

client = ApifyClient("YOUR_APIFY_TOKEN")
run = client.actor("sauliusautomatesit/threads-search-api").call(
    run_input={
        "searchQueries": ["web scraping"],
        "maxPostsPerQuery": 100,
        # "usernames": ["mosseri"],                                  # profiles
        # "postUrls": ["https://www.threads.com/@zuck/post/..."],    # a post with its replies
    },
    max_total_charge_usd=1,      # the run stops charging at $1
)
for post in client.dataset(run.default_dataset_id).iterate_items():
    if post["type"] == "post":
        print(post["likes"], post["username"], post["text"][:80])
```

This is `apify-client` 3.x, where `call()` returns a `Run` object. On 1.x and 2.x use
`run["defaultDatasetId"]`. From any other language, POST the same input to
`https://api.apify.com/v2/acts/sauliusautomatesit~threads-search-api/run-sync-get-dataset-items`
with an `Authorization: Bearer <token>` header and the posts come back in the response.

The Actor also takes post links (`postUrls`) and returns each post with its replies, replies to
replies included. The full input is on the
[Actor page](https://apify.com/sauliusautomatesit/threads-search-api).

## What it costs

Prices on 27 Oct 2026: **$2 per 1,000 posts** ($0.002 each) and the same per profile on Apify's free
plan, 5% to 15% less on paid plans, plus $0.00005 per run. 100 posts cost $0.20. Apify's free plan
includes $5 of usage a month.

## Notes

- Threads search returns what it shows a logged-out visitor for a keyword. That is usually the top
  posts for the term, not every post ever written with it.
- Posts and profiles are public data. Use them in line with Threads' terms and the privacy laws
  that apply to you.
- Something missing or wrong: open an issue here.

MIT licensed.
