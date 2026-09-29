"""XDA Developers article search inline plugin."""

from bs4 import BeautifulSoup
from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, in_pattern
from .__inline_utils import compact, html_text, web_document


@in_pattern("xda", owner=False)
async def xda_search(event):
    parts = str(getattr(event, "text", "") or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await event.answer([], switch_pm="Enter an XDA search query.", switch_pm_param="start")
    query = parts[1].strip()
    html = await async_searcher(
        "https://www.xda-developers.com/search/",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (compatible; Megatron/1.0)"},
        re_content=True,
    )
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for link in soup.select('a[href]'):
        href = link.get("href", "")
        if not href.startswith("http") or "xda-developers.com" not in href:
            continue
        title = link.get_text(" ", strip=True)
        if len(title) < 5 or href in seen:
            continue
        container = link.find_parent(["article", "div", "li"])
        description = ""
        image_url = None
        if container:
            p = container.find("p")
            description = compact(p.get_text(" ", strip=True) if p else "", 300)
            image = container.find("img")
            if image:
                image_url = image.get("src") or image.get("data-src")
        seen.add(href)
        img = web_document(image_url)
        text = f'<b><a href="{html_text(href, quote=True)}">{html_text(title)}</a></b>'
        if description:
            text += f"\n\n{html_text(description)}"
        results.append(
            await event.builder.article(
                title=compact(title, 256),
                description=description,
                url=href,
                thumb=img,
                text=text,
                parse_mode="html",
                link_preview=False,
                buttons=Button.switch_inline("Search again", query=f"xda {query}", same_peer=True),
            )
        )
        if len(results) >= 10:
            break

    await event.answer(
        results,
        cache_time=300,
        switch_pm=f"Found {len(results)} XDA results." if results else "No XDA results found.",
        switch_pm_param="start",
    )


InlinePlugin.update({"XDA Search": "xda "})
