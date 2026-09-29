"""npm package search inline plugin."""

from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, in_pattern
from .__inline_utils import compact, html_text


@in_pattern("npm", owner=False)
async def search_npm(event):
    query = str(getattr(event, "text", "") or "").split(None, 1)
    if len(query) < 2 or not query[1].strip():
        return await event.answer(
            [], switch_pm="Enter an npm package or keyword.", switch_pm_param="start"
        )

    term = query[1].strip()
    url = "https://registry.npmjs.org/-/v1/search"
    data = await async_searcher(
        url,
        re_json=True,
        params={"text": term, "size": 10},
        headers={"Accept": "application/json", "User-Agent": "Megatron"},
    )
    objects = data.get("objects", []) if isinstance(data, dict) else []
    results = []

    for obj in objects:
        package = obj.get("package") or {}
        name = package.get("name")
        if not name:
            continue
        version = package.get("version", "unknown")
        description = compact(package.get("description", "No description."), 300)
        npm_url = (package.get("links") or {}).get("npm") or f"https://www.npmjs.com/package/{name}"
        homepage = (package.get("links") or {}).get("homepage")
        keywords = package.get("keywords") or []
        text = (
            f"<b><a href=\"{html_text(npm_url, quote=True)}\">{html_text(name)}</a></b> "
            f"<code>{html_text(version)}</code>\n\n"
            f"{html_text(description)}"
        )
        if keywords:
            text += f"\n\n<b>Keywords:</b> {html_text(', '.join(map(str, keywords[:20])))}"
        buttons = [Button.url("npm", npm_url)]
        if homepage and homepage != npm_url:
            buttons.append(Button.url("Homepage", homepage))
        buttons.append(Button.switch_inline("Search again", query=f"npm {term}", same_peer=True))
        results.append(
            await event.builder.article(
                title=compact(name, 256),
                description=compact(f"{version} — {description}"),
                text=text,
                parse_mode="html",
                url=npm_url,
                link_preview=False,
                buttons=buttons,
            )
        )

    await event.answer(
        results,
        cache_time=300,
        switch_pm=f"Found {len(results)} npm packages." if results else "No npm packages found.",
        switch_pm_param="start",
    )


InlinePlugin.update({"npm Search": "npm "})
