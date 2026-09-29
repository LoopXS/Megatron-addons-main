"""PyPI package search and details inline plugin."""

import hashlib
import re
from time import monotonic
from bs4 import BeautifulSoup
from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, callback, in_pattern
from .__inline_utils import chunk_text, compact, html_text, web_document


_CACHE = {}
_CACHE_TTL = 900


def _cache_get(key):
    item = _CACHE.get(key)
    if not item:
        return None
    if monotonic() - item[0] > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return item[1]


def _cache_set(key, value):
    if len(_CACHE) > 500:
        _CACHE.pop(next(iter(_CACHE)))
    _CACHE[key] = (monotonic(), value)


def _package_text(info):
    name = info.get("name") or "Unknown"
    version = info.get("version") or "unknown"
    summary = compact(info.get("summary") or "No summary.", 500)
    url = info.get("package_url") or f"https://pypi.org/project/{name}/"
    text = (
        f'<b><a href="{html_text(url, quote=True)}">{html_text(name)}</a></b> '
        f'<code>{html_text(version)}</code>\n\n{html_text(summary)}'
    )
    author = info.get("author")
    if author:
        text += f"\n\n<b>Author:</b> {html_text(author)}"
    return text


@in_pattern("pypi", owner=False)
async def inline_pypi_handler(event):
    parts = str(getattr(event, "text", "") or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await event.answer(
            [
                await event.builder.article(
                    title="PyPI Search",
                    description="Search Python packages on PyPI.",
                    text="<b>PyPI Search</b>\n\nEnter a package name, for example: <code>pypi requests</code>",
                    parse_mode="html",
                    buttons=Button.switch_inline("Search again", query="pypi ", same_peer=True),
                )
            ]
        )

    package = parts[1].strip().split()[0]
    key = package.lower()
    response = _cache_get(key)
    if response is None:
        response = await async_searcher(
            f"https://pypi.org/pypi/{package}/json",
            re_json=True,
            headers={"Accept": "application/json", "User-Agent": "Megatron"},
        )
        if isinstance(response, dict) and response.get("info"):
            _cache_set(key, response)

    if not isinstance(response, dict) or not response.get("info"):
        return await event.answer(
            [
                await event.builder.article(
                    title="Package not found",
                    description=package,
                    text=f"<b>Package not found</b>\n\n<code>{html_text(package)}</code>",
                    parse_mode="html",
                    buttons=Button.switch_inline("Search again", query="pypi ", same_peer=True),
                )
            ],
            switch_pm=f"No PyPI package: {package}",
            switch_pm_param="start",
        )

    info = response["info"]
    name = info.get("name") or package
    version = info.get("version") or "unknown"
    package_url = info.get("package_url") or f"https://pypi.org/project/{name}/"
    description = compact(info.get("summary") or "No summary.", 400)
    qid = hashlib.sha256(f"{name.lower()}:{version}".encode()).hexdigest()[:8]
    readme = info.get("description") or ""
    links = []
    for key_name in ("home_page", "project_url"):
        value = info.get(key_name)
        if value and value.startswith(("http://", "https://")) and value not in links:
            links.append(value)
    project_urls = info.get("project_urls") or {}
    for value in project_urls.values():
        if value and str(value).startswith(("http://", "https://")) and value not in links:
            links.append(value)

    _cache_set(
        f"detail:{qid}",
        {
            "name": name,
            "version": version,
            "url": package_url,
            "info": info,
            "readme": readme,
            "links": links[:20],
            "summary": description,
        },
    )

    buttons = [
        [Button.inline("Details", data=f"pypi:details:{qid}"), Button.inline("Description", data=f"pypi:desc:{qid}:1")],
    ]
    if links:
        buttons.append([Button.url("Project link", links[0])])
    buttons.append([Button.switch_inline("Search again", query=f"pypi {name}", same_peer=True)])

    await event.answer(
        [
            await event.builder.article(
                title=compact(name, 256),
                description=compact(f"{version} — {description}"),
                url=package_url,
                text=_package_text(info),
                parse_mode="html",
                buttons=buttons,
                link_preview=False,
            )
        ],
        cache_time=600,
        switch_pm=f"PyPI: {name}",
        switch_pm_param="start",
    )


@callback(re.compile(r"pypi:details:([0-9a-f]{8})"), owner=False)
async def show_details(event):
    qid = event.pattern_match.group(1).decode()
    item = _cache_get(f"detail:{qid}")
    if not item:
        return await event.answer("This result expired. Search again.", alert=True)
    info = item["info"]
    text = _package_text(info)
    for label, key in (
        ("License", "license"),
        ("Python", "requires_python"),
        ("Downloads", "downloads"),
    ):
        value = info.get(key)
        if value:
            text += f"\n<b>{label}:</b> {html_text(compact(value, 500))}"
    classifiers = info.get("classifiers") or []
    if classifiers:
        relevant = [x for x in classifiers if x.startswith(("Programming Language :: Python", "License ::", "Operating System ::"))]
        if relevant:
            text += "\n\n<b>Classifiers:</b>\n" + "\n".join(f"• {html_text(x)}" for x in relevant[:20])
    await event.edit(
        text,
        parse_mode="html",
        buttons=[
            [Button.inline("Description", data=f"pypi:desc:{qid}:1")],
            [Button.inline("Back", data=f"pypi:back:{qid}")],
        ],
    )


@callback(re.compile(r"pypi:desc:([0-9a-f]{8}):(\d+)"), owner=False)
async def show_description(event):
    qid = event.pattern_match.group(1).decode()
    page = max(1, int(event.pattern_match.group(2).decode()))
    item = _cache_get(f"detail:{qid}")
    if not item:
        return await event.answer("This result expired. Search again.", alert=True)

    raw = item.get("readme") or "No description is available."
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text("\n", strip=True) if "<" in raw else raw
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    pages = chunk_text(text, 2800)
    page = min(page, len(pages))
    body = pages[page - 1]
    rendered = f"<b>Description</b> · <code>{page}/{len(pages)}</code>\n\n{html_text(body)}"

    nav = []
    if page > 1:
        nav.append(Button.inline("‹", data=f"pypi:desc:{qid}:{page - 1}"))
    nav.append(Button.inline("Back", data=f"pypi:back:{qid}"))
    if page < len(pages):
        nav.append(Button.inline("›", data=f"pypi:desc:{qid}:{page + 1}"))
    await event.edit(rendered, parse_mode="html", buttons=[nav])


@callback(re.compile(r"pypi:back:([0-9a-f]{8})"), owner=False)
async def back_to_package(event):
    qid = event.pattern_match.group(1).decode()
    item = _cache_get(f"detail:{qid}")
    if not item:
        return await event.answer("This result expired. Search again.", alert=True)
    info = item["info"]
    buttons = [
        [Button.inline("Details", data=f"pypi:details:{qid}"), Button.inline("Description", data=f"pypi:desc:{qid}:1")],
    ]
    await event.edit(_package_text(info), parse_mode="html", buttons=buttons)


InlinePlugin.update({"PyPI Search": "pypi "})
