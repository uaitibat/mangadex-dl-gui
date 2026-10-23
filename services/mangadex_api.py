from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from services.models import (
    ChapterGroup,
    ChapterPages,
    MangaDetails,
    MangaSummary,
    MdListDetails,
    UserMdList,
    UserProfile,
)


API_BASE_URL = "https://api.mangadex.org"
AUTH_TOKEN_URL = "https://auth.mangadex.org/realms/mangadex/protocol/openid-connect/token"
COVER_BASE_URL = "https://uploads.mangadex.org/covers"
MEDIA_BASE_URL = "https://uploads.mangadex.org/media"


class MangaDexApiError(RuntimeError):
    pass


class MangaDexApiClient:
    def __init__(self, access_token: str | None = None) -> None:
        self.access_token = access_token

    def load_from_url(self, url: str) -> MangaDetails | MdListDetails:
        resource_type, resource_id = self.parse_mangadex_url(url)
        if resource_type == "title":
            return self.get_manga(resource_id)
        if resource_type == "list":
            return self.get_mdlist(resource_id)
        raise MangaDexApiError("URL do MangaDex nao suportada.")

    def login(
        self,
        username: str,
        password: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        payload = urllib.parse.urlencode(
            {
                "grant_type": "password",
                "username": username,
                "password": password,
                "client_id": client_id,
                "client_secret": client_secret,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            AUTH_TOKEN_URL,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": "MangaDex-dl GTK prototype",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            raise MangaDexApiError(f"Login falhou HTTP {error.code}: {message}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise MangaDexApiError(f"Falha ao fazer login: {error}") from error

        access_token = data.get("access_token")
        if not access_token:
            raise MangaDexApiError("Login nao retornou access_token.")
        self.access_token = access_token

    def get_me(self) -> UserProfile:
        payload = self._get("/user/me")
        data = payload["data"]
        attributes = data.get("attributes", {})
        return UserProfile(
            id=data["id"],
            username=attributes.get("username") or "MangaDex user",
            avatar_url=self._user_media_url(data, "avatar"),
            banner_url=self._user_media_url(data, "banner"),
        )

    def get_user_mdlists(self, user_id: str) -> list[UserMdList]:
        lists: list[UserMdList] = []
        offset = 0
        limit = 100
        while True:
            payload = self._get(f"/user/{user_id}/list", {"limit": limit, "offset": offset})
            for item in payload.get("data", []):
                attributes = item.get("attributes", {})
                lists.append(
                    UserMdList(
                        id=item["id"],
                        name=attributes.get("name") or "MDList",
                        visibility=attributes.get("visibility") or "unknown",
                        manga=[],
                    )
                )

            total = payload.get("total", len(lists))
            offset += limit
            if offset >= total:
                break
        return lists

    def get_user_mdlists_with_manga(self, user_id: str) -> list[UserMdList]:
        lists = self.get_user_mdlists(user_id)
        hydrated: list[UserMdList] = []
        for mdlist in lists:
            details = self.get_mdlist(mdlist.id)
            hydrated.append(
                UserMdList(
                    id=mdlist.id,
                    name=mdlist.name,
                    visibility=mdlist.visibility,
                    manga=details.manga,
                    source=mdlist.source,
                )
            )
        return hydrated

    def get_my_mdlists_with_manga(self, include_followed: bool = True) -> list[UserMdList]:
        lists = self._get_mdlists_from_endpoint("/user/list", "minha")
        if include_followed:
            lists.extend(self._get_mdlists_from_endpoint("/user/follows/list", "seguida"))

        if not lists:
            return []

        # busca detalhes das listas em paralelo (3 threads) para abrir mais rápido
        def _fetch(mdlist: UserMdList) -> UserMdList:
            details = self.get_mdlist(mdlist.id)
            return UserMdList(
                id=mdlist.id,
                name=mdlist.name,
                visibility=mdlist.visibility,
                manga=details.manga,
                source=mdlist.source,
            )

        hydrated: list[UserMdList] = []
        with ThreadPoolExecutor(max_workers=4) as ex:
            futures = {ex.submit(_fetch, m): m for m in lists}
            for fut in as_completed(futures):
                try:
                    hydrated.append(fut.result())
                except Exception:
                    # mantém lista mesmo se uma falhar
                    m = futures[fut]
                    hydrated.append(UserMdList(id=m.id, name=m.name, visibility=m.visibility, manga=[], source=m.source))
        # mantém ordem original (minha primeiro)
        order = {m.id: i for i, m in enumerate(lists)}
        hydrated.sort(key=lambda x: order.get(x.id, 999))
        return hydrated

    def _get_mdlists_from_endpoint(self, path: str, source: str) -> list[UserMdList]:
        lists: list[UserMdList] = []
        offset = 0
        limit = 100
        while True:
            payload = self._get(path, {"limit": limit, "offset": offset})
            lists.extend(self._parse_mdlist_collection(payload, source))
            total = payload.get("total", len(lists))
            offset += limit
            if offset >= total:
                break
        return lists

    def _parse_mdlist_collection(self, payload: dict[str, Any], source: str) -> list[UserMdList]:
        lists: list[UserMdList] = []
        for item in payload.get("data", []):
            attributes = item.get("attributes", {})
            lists.append(
                UserMdList(
                    id=item["id"],
                    name=attributes.get("name") or "MDList",
                    visibility=attributes.get("visibility") or "unknown",
                    manga=[],
                    source=source,
                )
            )
        return lists

    def get_manga(self, manga_id: str) -> MangaDetails:
        payload = self._get(f"/manga/{manga_id}", {"includes[]": ["cover_art"]})
        data = payload["data"]
        attributes = data.get("attributes", {})
        return MangaDetails(
            id=data["id"],
            title=self._localized_text(attributes.get("title", {})),
            description=self._localized_text(attributes.get("description", {})),
            tags=self._tag_names(attributes.get("tags", [])),
            year=attributes.get("year"),
            status=attributes.get("status"),
            cover_url=self._cover_url_for_manga(data),
            descriptions=attributes.get("description", {}),
        )

    def _tag_names(self, tags: list[dict[str, Any]]) -> list[str]:
        names: list[str] = []
        for tag in tags:
            attributes = tag.get("attributes", {})
            name = self._localized_text(attributes.get("name", {}))
            if name:
                names.append(name)
        return names

    def get_manga_chapters(self, manga_id: str) -> list[ChapterGroup]:
        chapters: list[ChapterGroup] = []
        offset = 0
        limit = 100
        while True:
            payload = self._get(
                f"/manga/{manga_id}/feed",
                {
                    "limit": limit,
                    "offset": offset,
                    "includes[]": ["scanlation_group"],
                    "order[chapter]": "desc",
                    "contentRating[]": ["safe", "suggestive", "erotica", "pornographic"],
                },
            )
            for item in payload.get("data", []):
                attributes = item.get("attributes", {})
                volume = attributes.get("volume") or "Sem volume"
                chapter = attributes.get("chapter") or "Extra"
                title = attributes.get("title") or ""
                language = attributes.get("translatedLanguage")
                groups: list[str] = []

                for relation in item.get("relationships", []):
                    if relation.get("type") == "scanlation_group":
                        name = relation.get("attributes", {}).get("name")
                        if name:
                            groups.append(name)

                chapters.append(
                    ChapterGroup(
                        id=item["id"],
                        volume=str(volume),
                        chapter=str(chapter),
                        title=str(title),
                        languages=[language] if language else [],
                        groups=groups,
                        updated_at=attributes.get("updatedAt") or attributes.get("publishAt"),
                    )
                )

            total = payload.get("total", offset + len(payload.get("data", [])))
            offset += limit
            if offset >= total:
                break

        chapters.sort(key=lambda item: self._sort_number(item.chapter), reverse=True)
        return chapters

    def get_chapter_pages(self, chapter_id: str) -> ChapterPages:
        payload = self._get(f"/at-home/server/{chapter_id}")
        base_url = payload.get("baseUrl")
        chapter = payload.get("chapter", {})
        chapter_hash = chapter.get("hash")
        files = chapter.get("data") or []
        if not base_url or not chapter_hash or not files:
            raise MangaDexApiError("Nao encontrei paginas para esse capitulo.")

        pages = [
            f"{base_url}/data/{chapter_hash}/{file_name}"
            for file_name in files
            if file_name
        ]
        return ChapterPages(chapter_id=chapter_id, hash=chapter_hash, pages=pages)

    def get_mdlist(self, list_id: str) -> MdListDetails:
        payload = self._get(f"/list/{list_id}")
        data = payload["data"]
        attributes = data.get("attributes", {})
        manga_ids = [
            relation["id"]
            for relation in data.get("relationships", [])
            if relation.get("type") == "manga"
        ]
        return MdListDetails(
            id=data["id"],
            name=attributes.get("name") or "MDList",
            manga=self.get_manga_batch(manga_ids),
        )

    def get_manga_batch(self, manga_ids: list[str]) -> list[MangaSummary]:
        if not manga_ids:
            return []

        manga: list[MangaSummary] = []
        for offset in range(0, len(manga_ids), 100):
            chunk = manga_ids[offset : offset + 100]
            payload = self._get(
                "/manga",
                {
                    "ids[]": chunk,
                    "includes[]": ["cover_art"],
                    "limit": len(chunk),
                },
            )
            for item in payload.get("data", []):
                attributes = item.get("attributes", {})
                manga.append(
                    MangaSummary(
                        id=item["id"],
                        title=self._localized_text(attributes.get("title", {})),
                        cover_url=self._cover_url_for_manga(item),
                    )
                )
        return manga

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        query = urllib.parse.urlencode(params or {}, doseq=True)
        url = f"{API_BASE_URL}{path}"
        if query:
            url = f"{url}?{query}"

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "MangaDex-dl GTK prototype",
                **self._auth_headers(),
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            raise MangaDexApiError(f"MangaDex respondeu HTTP {error.code}: {message}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise MangaDexApiError(f"Falha ao acessar MangaDex: {error}") from error

    def _auth_headers(self) -> dict[str, str]:
        if not self.access_token:
            return {}
        return {"Authorization": f"Bearer {self.access_token}"}

    def _cover_url_for_manga(self, manga: dict[str, Any]) -> str | None:
        manga_id = manga.get("id")
        for relation in manga.get("relationships", []):
            if relation.get("type") != "cover_art":
                continue
            file_name = relation.get("attributes", {}).get("fileName")
            if file_name:
                return f"{COVER_BASE_URL}/{manga_id}/{file_name}.512.jpg"
        return None

    def _user_media_url(self, user: dict[str, Any], media_type: str) -> str | None:
        user_id = user.get("id")
        attributes = user.get("attributes", {})
        file_key = f"{media_type}FileName"
        file_name = attributes.get(file_key)
        if not user_id or not file_name:
            return None
        return f"{MEDIA_BASE_URL}/user/{user_id}/{media_type}/{file_name}"

    def _localized_text(self, values: dict[str, str]) -> str:
        for language in ("pt-br", "en", "ja-ro", "ja"):
            value = values.get(language)
            if value:
                return value
        for value in values.values():
            if value:
                return value
        return ""

    def _sort_number(self, value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return -1.0

    def parse_mangadex_url(self, url: str) -> tuple[str, str]:
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() not in {"mangadex.org", "www.mangadex.org"}:
            raise MangaDexApiError("Use uma URL do mangadex.org.")

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise MangaDexApiError("URL do MangaDex incompleta.")

        resource_type = parts[0]
        resource_id = parts[1]
        if resource_type not in {"title", "list"}:
            raise MangaDexApiError("Por enquanto aceito URL de title ou list.")
        return resource_type, resource_id
