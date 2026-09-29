"""OMG! Ubuntu article search inline plugin."""

from bs4 import BeautifulSoup
from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, in_pattern
from .__inline_utils import compact, html_text, web_document


@in_pattern("omgu", owner=False)
async def omgubuntu(event):
    parts = str(getattr(event, "text", "") or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await event.answer([], switch_pm="Enter a search query.", switch_pm_param="start")
    query = parts[1].strip()
    html = await async_searcher(
        "https://www.omgubuntu.co.uk/",
        params={"s": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; Megatron/1.0)"},
        re_content=True,
    )
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for article in soup.select("article"):
        link = article.find("a", href=True)
        heading = article.find(["h1", "h2", "h3", "h4"])
        if not link or not heading:
            continue
        url = link.get("href")
        title = heading.get_text(" ", strip=True)
        if not url or not title or url in seen:
            continue
        seen.add(url)
        description_node = article.find("p")
        description = compact(description_node.get_text(" ", strip=True) if description_node else "", 350)
        image = article.find("img")
        image_url = image.get("src") or image.get("data-src") if image else None
        img = web_document(image_url)
        text = f'<b><a href="{html_text(url, quote=True)}">{html_text(title)}</a></b>'
        if description:
            text += f"\n\n{html_text(description)}"
        results.append(
            await event.builder.article(
                title=compact(title, 256),
                description=description,
                url=url,
                text=text,
                parse_mode="html",
                thumb=img,
                link_preview=False,
                buttons=Button.switch_inline("Search again", query=f"omgu {query}", same_peer=True),
            )
        )
        if len(results) >= 10:
            break

    await event.answer(
        results,
        cache_time=300,
        switch_pm=f"Found {len(results)} articles." if results else "No articles found.",
        switch_pm_param="start",
    )


InlinePlugin.update({"OMG Ubuntu Search": "omgu "})
