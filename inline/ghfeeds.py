"""GitHub user activity inline search."""

from html import escape

from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, in_pattern
from .__inline_utils import compact, html_text, web_document


@in_pattern("gh", owner=False)
async def gh_feeds(event):
    query = str(getattr(event, "text", "") or "").split(None, 1)
    if len(query) < 2 or not query[1].strip():
        return await event.answer(
            [],
            switch_pm="Enter a GitHub username. Example: gh octocat",
            switch_pm_param="start",
        )

    username = query[1].strip().lstrip("@").rstrip(".").split()[0]
    if not username or any(c in username for c in "/\\"):
        return await event.answer(
            [], switch_pm="Invalid GitHub username.", switch_pm_param="start"
        )

    data = await async_searcher(
        f"https://api.github.com/users/{username}/events/public",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "Megatron"},
        re_json=True,
    )

    if not isinstance(data, list):
        message = data.get("message", "GitHub API returned an error.") if isinstance(data, dict) else "GitHub API returned an error."
        return await event.answer(
            [
                await event.builder.article(
                    title="GitHub Error",
                    description=compact(message),
                    text=f"<b>GitHub Error</b>\n\n{html_text(message)}",
                    parse_mode="html",
                    buttons=Button.switch_inline("Search again", query="gh ", same_peer=True),
                )
            ],
            cache_time=30,
            switch_pm="GitHub request failed.",
            switch_pm_param="start",
        )

    results = []
    seen = set()
    for item in data[:50]:
        event_type = item.get("type")
        repo = (item.get("repo") or {}).get("name")
        if not repo:
            continue
        repo_url = f"https://github.com/{repo}"
        actor = (item.get("actor") or {}).get("login") or username
        actor_url = f"https://github.com/{actor}"
        payload = item.get("payload") or {}
        action = None
        target_url = repo_url
        extra = ""

        if event_type == "PushEvent":
            action = "pushed commits to"
            commits = payload.get("commits") or []
            if commits:
                last = commits[-1]
                target_url = last.get("url") or repo_url
                extra = f"\n<b>Commit:</b> {html_text(compact(last.get('message'), 240))}"
        elif event_type == "IssueCommentEvent":
            action = "commented on an issue in"
            target_url = (payload.get("comment") or {}).get("html_url") or repo_url
        elif event_type == "CreateEvent":
            action = "created a ref in"
        elif event_type == "PullRequestEvent":
            action = "updated a pull request in"
            target_url = (payload.get("pull_request") or {}).get("html_url") or repo_url
        elif event_type == "ForkEvent":
            action = "forked"
            target_url = (payload.get("forkee") or {}).get("html_url") or repo_url
        elif event_type == "WatchEvent":
            action = "starred"
        elif event_type == "IssuesEvent":
            action = f"{payload.get('action', 'updated')} an issue in"
            target_url = (payload.get("issue") or {}).get("html_url") or repo_url
        else:
            continue

        key = (event_type, target_url)
        if key in seen:
            continue
        seen.add(key)

        title = f"@{actor} {action} {repo}"
        text = (
            f'<b><a href="{escape(actor_url, quote=True)}">@{html_text(actor)}</a></b> '
            f'{html_text(action)} '
            f'<b><a href="{escape(repo_url, quote=True)}">{html_text(repo)}</a></b>'
            f"{extra}"
        )
        results.append(
            await event.builder.article(
                title=compact(title, 256),
                description=compact(repo),
                text=text,
                parse_mode="html",
                url=target_url,
                thumb=web_document((item.get("actor") or {}).get("avatar_url")),
                link_preview=False,
                buttons=[
                    Button.url("View", target_url),
                    Button.switch_inline("Search again", query=f"gh {username}", same_peer=True),
                ],
            )
        )

    await event.answer(
        results,
        cache_time=300,
        switch_pm=f"Showing {len(results)} GitHub events." if results else "No public events found.",
        switch_pm_param="start",
    )


InlinePlugin.update({"GitHub Feeds": "gh "})
