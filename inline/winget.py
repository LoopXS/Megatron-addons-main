"""WinGet / Microsoft Store package search inline plugin.

Uses the REST source used by the WinGet client instead of the retired
api.winget.run service. The endpoint is the Microsoft Store REST source
and returns package identifiers that can be installed through WinGet's
`msstore` source.
"""

import asyncio

from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, in_pattern
from .__inline_utils import compact, html_text


SEARCH_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/manifestSearch"
MANIFEST_URL = "https://storeedgefd.dsx.mp.microsoft.com/v9.0/packageManifests/{}"


async def _manifest(package_id):
    data = await async_searcher(
        MANIFEST_URL.format(package_id),
        re_json=True,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Megatron/1.0",
        },
    )
    return data if isinstance(data, dict) else None


def _extract_manifest(data):
    root = data.get("Data") if isinstance(data, dict) else None
    if not isinstance(root, dict):
        return {}
    versions = root.get("Versions") or []
    latest = versions[-1] if versions and isinstance(versions[-1], dict) else {}
    locale = latest.get("DefaultLocale") or {}
    return {
        "description": locale.get("ShortDescription") or locale.get("Description") or "",
        "publisher": locale.get("Publisher") or "",
        "homepage": locale.get("PackageUrl") or locale.get("PublisherUrl") or "",
        "version": latest.get("PackageVersion") or "",
    }


@in_pattern("winget", owner=False)
async def search_winget(event):
    parts = str(getattr(event, "text", "") or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await event.answer(
            [],
            switch_pm="Enter a Microsoft Store app name. Example: winget vscode",
            switch_pm_param="start",
        )

    query = parts[1].strip()
    payload = {"Query": {"KeyWord": query, "MatchType": "Substring"}}
    data = await async_searcher(
        SEARCH_URL,
        post=True,
        json=payload,
        re_json=True,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Megatron/1.0",
        },
    )
    rows = data.get("Data", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []

    rows = [row for row in rows if isinstance(row, dict) and row.get("PackageIdentifier")][:10]
    manifests = await asyncio.gather(
        *(_manifest(row["PackageIdentifier"]) for row in rows),
        return_exceptions=True,
    )

    results = []
    for row, manifest in zip(rows, manifests):
        package_id = str(row.get("PackageIdentifier"))
        name = row.get("PackageName") or package_id
        publisher = row.get("Publisher") or ""
        details = _extract_manifest(manifest) if isinstance(manifest, dict) else {}
        description = compact(details.get("description") or "No description available.", 500)
        version = details.get("version") or "unknown"
        text = (
            f"<b>{html_text(name)}</b>\n"
            f"<code>{html_text(package_id)}</code>\n\n"
            f"{html_text(description)}\n\n"
            f"<b>Version:</b> <code>{html_text(version)}</code>"
        )
        if publisher:
            text += f"\n<b>Publisher:</b> {html_text(publisher)}"
        text += f"\n<b>Install:</b> <code>winget install --id {html_text(package_id)} --source msstore</code>"

        buttons = [
            Button.switch_inline("Search again", query=f"winget {query}", same_peer=True)
        ]
        if package_id:
            buttons.insert(0, Button.url("Microsoft Store", f"https://apps.microsoft.com/detail/{package_id}"))

        results.append(
            await event.builder.article(
                title=compact(name, 256),
                description=compact(description),
                text=text,
                parse_mode="html",
                url=f"https://apps.microsoft.com/detail/{package_id}",
                link_preview=False,
                buttons=buttons,
            )
        )

    await event.answer(
        results,
        cache_time=300,
        switch_pm=(
            f"Found {len(results)} Microsoft Store packages."
            if results
            else "No Microsoft Store packages found."
        ),
        switch_pm_param="start",
    )


InlinePlugin.update({"WinGet Search": "winget "})
