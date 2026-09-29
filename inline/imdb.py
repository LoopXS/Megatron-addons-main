"""IMDb/OMDb movie search inline plugin."""

import hashlib
import re
from time import monotonic
from urllib.parse import quote_plus

from telethon.tl.custom import Button

from . import InlinePlugin, async_searcher, callback, in_pattern, udB
from .__inline_utils import chunk_text, compact, html_text, web_document


CACHE = {}
TTL = 1800
POSTER_FALLBACK = "https://graph.org/file/3b45a9ed4868167954300.jpg"


def _get(key):
    item = CACHE.get(key)
    if not item:
        return None
    if monotonic() - item[0] > TTL:
        CACHE.pop(key, None)
        return None
    return item[1]


def _set(key, value):
    if len(CACHE) > 500:
        CACHE.pop(next(iter(CACHE)))
    CACHE[key] = (monotonic(), value)


def _parse_query(raw):
    raw = raw.strip()
    match = re.match(r"^(.*?)\s+y\s*=\s*(\d{4})$", raw, re.I)
    if match:
        return match.group(1).strip(), match.group(2)
    match = re.match(r"^(.*?)\s+y\s*=\s*$", raw, re.I)
    if match:
        return match.group(1).strip(), None
    return raw, None


async def get_movie_data(search_term, full_plot=False):
    api_key = udB.get_key("OMDB")
    if not api_key:
        return None, "OMDB API key is not configured."
    title, year = _parse_query(search_term)
    params = {"apikey": api_key, "t": title, "plot": "full" if full_plot else "short"}
    if year:
        params["y"] = year
    data = await async_searcher(
        "https://www.omdbapi.com/",
        params=params,
        re_json=True,
        headers={"Accept": "application/json", "User-Agent": "Megatron"},
    )
    if isinstance(data, dict) and data.get("Response") == "True":
        return data, None
    return None, (data or {}).get("Error", "Movie not found.") if isinstance(data, dict) else "Movie not found."


@in_pattern("imdb", owner=False)
async def inline_imdb_command(event):
    parts = str(getattr(event, "text", "") or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await event.answer(
            [
                await event.builder.article(
                    title="IMDb Search",
                    description="Search movies and series.",
                    text="<b>IMDb Search</b>\n\nEnter a title. Example: <code>imdb Inception</code>",
                    parse_mode="html",
                    buttons=Button.switch_inline("Search again", query="imdb ", same_peer=True),
                )
            ]
        )

    query = parts[1].strip()
    data, error = await get_movie_data(query)
    if not data:
        text = f"<b>IMDb search failed</b>\n\n{html_text(error)}"
        return await event.answer(
            [
                await event.builder.article(
                    title="No result",
                    description=compact(error),
                    text=text,
                    parse_mode="html",
                    buttons=Button.switch_inline("Search again", query="imdb ", same_peer=True),
                )
            ],
            switch_pm=compact(error, 200),
            switch_pm_param="start",
        )

    imdb_id = data.get("imdbID")
    poster = data.get("Poster") if data.get("Poster") not in (None, "N/A") else POSTER_FALLBACK
    key = f"movie:{imdb_id or hashlib.sha256(query.lower().encode()).hexdigest()[:12]}"
    _set(key, data)

    title = data.get("Title") or query
    released = data.get("Released") or "N/A"
    country = data.get("Country") or "N/A"
    rating = data.get("imdbRating") or "N/A"
    genre = data.get("Genre") or "N/A"
    language = data.get("Language") or "N/A"
    plot = compact(data.get("Plot") or "No plot available.", 900)
    text = (
        f"<b>{html_text(title)}</b> <code>{html_text(data.get('Year', ''))}</code>\n\n"
        f"<b>Released:</b> {html_text(released)}\n"
        f"<b>Rating:</b> <code>{html_text(rating)}</code>\n"
        f"<b>Genre:</b> {html_text(genre)}\n"
        f"<b>Country:</b> {html_text(country)}\n"
        f"<b>Language:</b> {html_text(language)}\n\n"
        f"{html_text(plot)}"
    )
    buttons = [[Button.inline("Full details", data=f"imdb:details:{key.split(':',1)[1]}"), Button.switch_inline("Search again", query="imdb ", same_peer=True)]]
    if imdb_id:
        buttons.append([Button.url("IMDb", f"https://www.imdb.com/title/{imdb_id}/")])

    img = web_document(poster)
    article_kwargs = dict(
        title=compact(title, 256),
        description=compact(f"{data.get('Year', '')} · IMDb {rating} · {genre}"),
        text=text,
        parse_mode="html",
        buttons=buttons,
        link_preview=False,
    )
    if img:
        article_kwargs.update(type="photo", include_media=True, content=img, thumb=img)
    await event.answer([await event.builder.article(**article_kwargs)], cache_time=600)


@callback(re.compile(r"imdb:details:(.+)"), owner=False)
async def movie_details(event):
    movie_id = event.pattern_match.group(1).decode()
    data = _get(f"movie:{movie_id}")
    if not data:
        return await event.answer("This result expired. Search again.", alert=True)
    fields = [
        ("Title", data.get("Title")),
        ("Year", data.get("Year")),
        ("Rated", data.get("Rated")),
        ("Released", data.get("Released")),
        ("Runtime", data.get("Runtime")),
        ("Genre", data.get("Genre")),
        ("Director", data.get("Director")),
        ("Actors", data.get("Actors")),
        ("Writer", data.get("Writer")),
        ("Country", data.get("Country")),
        ("Language", data.get("Language")),
        ("Awards", data.get("Awards")),
        ("IMDb rating", data.get("imdbRating")),
        ("IMDb votes", data.get("imdbVotes")),
        ("Box office", data.get("BoxOffice")),
    ]
    text = "<b>IMDb Details</b>\n\n" + "\n".join(
        f"<b>{html_text(label)}:</b> {html_text(value)}" for label, value in fields if value not in (None, "", "N/A")
    )
    text += f"\n\n<b>Plot</b>\n{html_text(data.get('Plot') or 'N/A')}"
    buttons = [[Button.inline("Back", data=f"imdb:back:{movie_id}")]]
    imdb_id = data.get("imdbID")
    if imdb_id:
        buttons.insert(0, [Button.url("IMDb", f"https://www.imdb.com/title/{imdb_id}/")])
    await event.edit(text, parse_mode="html", buttons=buttons)


@callback(re.compile(r"imdb:back:(.+)"), owner=False)
async def movie_back(event):
    movie_id = event.pattern_match.group(1).decode()
    data = _get(f"movie:{movie_id}")
    if not data:
        return await event.answer("This result expired. Search again.", alert=True)
    title = data.get("Title") or "Movie"
    rating = data.get("imdbRating") or "N/A"
    text = (
        f"<b>{html_text(title)}</b> <code>{html_text(data.get('Year', ''))}</code>\n\n"
        f"<b>Released:</b> {html_text(data.get('Released'))}\n"
        f"<b>Rating:</b> <code>{html_text(rating)}</code>\n"
        f"<b>Genre:</b> {html_text(data.get('Genre'))}\n\n"
        f"{html_text(compact(data.get('Plot') or 'No plot available.', 900))}"
    )
    await event.edit(
        text,
        parse_mode="html",
        buttons=[[Button.inline("Full details", data=f"imdb:details:{movie_id}")]],
    )


InlinePlugin.update({"IMDb Search": "imdb "})
