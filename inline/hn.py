"""Hacker News story search using the public Algolia API."""

from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, in_pattern
from .__inline_utils import compact, html_text


API_URL = "https://hn.algolia.com/api/v1/search"


@in_pattern("hn", owner=False)
async def hacker_news_search(event):
    parts = str(getattr(event, "text", "") or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await event.answer(
            [],
            switch_pm="Enter a Hacker News search query. Example: hn python",
            switch_pm_param="start",
        )

    query = parts[1].strip()
    data = await async_searcher(
        API_URL,
        params={"query": query, "tags": "story", "hitsPerPage": 10},
        re_json=True,
        headers={"Accept": "application/json", "User-Agent": "Megatron/1.0"},
    )
    hits = data.get("hits", []) if isinstance(data, dict) else []
    if not isinstance(hits, list):
        hits = []

    results = []
    for hit in hits[:10]:
        if not isinstance(hit, dict):
            continue
        title = hit.get("title") or hit.get("story_title") or "Untitled story"
        object_id = hit.get("objectID")
        if not object_id:
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"
        author = hit.get("author") or "unknown"
        points = hit.get("points")
        comments = hit.get("num_comments")
        text = f"<b>{html_text(title)}</b>\n\n"
        text += f"<b>Author:</b> {html_text(author)}"
        if points is not None:
            text += f"\n<b>Points:</b> {html_text(points)}"
        if comments is not None:
            text += f"\n<b>Comments:</b> {html_text(comments)}"
        text += f"\n\n<a href=\"https://news.ycombinator.com/item?id={html_text(object_id, quote=True)}\">Open on Hacker News</a>"

        results.append(
            await event.builder.article(
                title=compact(title, 256),
                description=compact(f"by {author}"),
                url=url,
                text=text,
                parse_mode="html",
                link_preview=False,
                buttons=[
                    Button.url("Open", url),
                    Button.switch_inline("Search again", query=f"hn {query}", same_peer=True),
                ],
            )
        )

    await event.answer(
        results,
        cache_time=300,
        switch_pm=f"Found {len(results)} Hacker News stories." if results else "No stories found.",
        switch_pm_param="start",
    )


InlinePlugin.update({"Hacker News Search": "hn "})
