from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from services.models import ChapterGroup, ChapterPages, MangaDetails

API_BASE_URLS = ["https://api.comick.io", "https://api.comick.dev", "https://comickz.co.uk", "https://comick.live"]
API_BASE_URL = API_BASE_URLS[0]
IMAGE_BASE_URL = "https://meo.comick.pictures"
SITE_URLS = ["https://comick.io", "https://comick.dev", "https://comickz.co.uk", "https://comick.live"]
SITE_URL = SITE_URLS[0]


class ComickApiError(RuntimeError):
    pass


class ComickApiClient:
    def __init__(self) -> None:
        self._last_slug: str | None = None
        self._last_site: str | None = None
        self._chapter_map: dict[str, tuple[str, str, str]] = {}  # hid -> (slug, chap, lang)

    def load_from_url(self, url: str) -> MangaDetails:
        resource_type, resource_id = self.parse_comick_url(url)
        if resource_type == "comic":
            return self.get_manga(resource_id)
        raise ComickApiError("URL do Comick nao suportada.")

    def _parse_comic_data(self, comic_data: dict[str, Any], comic_hid: str) -> MangaDetails:
        title = comic_data.get("title") or "Sem título"
        description = comic_data.get("desc") or comic_data.get("parsed") or ""
        # limpa html tags se vier de parsed
        if description and "<" in description:
            import re as _re
            description = _re.sub(r"<[^>]+>", "", description)
        cover_url = None
        md_covers = comic_data.get("md_covers", [])
        if md_covers:
            b2key = md_covers[0].get("b2key")
            if b2key:
                cover_url = f"{IMAGE_BASE_URL}/{b2key}"
        if not cover_url:
            # comickz usa default_thumbnail direto
            for k in ("default_thumbnail", "thumbnail", "cover_url", "image_url"):
                v = comic_data.get(k)
                if isinstance(v, str) and v.startswith("http"):
                    cover_url = v
                    break
        # guarda mapeamento hid <-> slug para capítulos comickz
        hid = comic_data.get("hid") or comic_hid
        slug = comic_data.get("slug") or comic_hid
        if hid and slug:
            self._chapter_map[hid] = (slug, "", "")
            # também mapeia slug -> slug para fallback
            self._chapter_map[slug] = (slug, "", "")
            self._last_slug = slug
            self._last_site = "https://comickz.co.uk" if "comickz" in str(comic_data) or "cdn1.comicknew" in str(comic_data) else self._last_site
            if slug and hid != slug:
                # guarda ambos
                self._last_slug = slug
        tags = []
        for genre in comic_data.get("md_comic_md_genres", []):
            gd = genre.get("md_genres")
            if gd:
                tags.append(gd.get("name", ""))
        status_map = {1: "Ongoing", 2: "Completed", 3: "Cancelled", 4: "On Hiatus"}
        status = status_map.get(comic_data.get("status"))
        year = comic_data.get("year")
        return MangaDetails(
            id=comic_data.get("hid", comic_hid),
            title=title,
            description=description,
            tags=tags if tags else None,
            year=year,
            status=status,
            cover_url=cover_url,
            descriptions={"en": description} if description else None,
        )

    def _is_cloudflare_challenge(self, html: str, status: int | None = None) -> bool:
        return (
            status == 403
            or "Just a moment" in html
            or "challenges.cloudflare.com" in html
            or "cf-chl-opt" in html
            or "Enable JavaScript and cookies to continue" in html
        )

    def _fetch_html_with_retry(self, url: str, retries: int = 3) -> str:
        last_err = None
        # tenta todos os SITE_URLs
        urls_to_try = [url]
        for alt_base in SITE_URLS:
            alt = url.replace(SITE_URL, alt_base) if url.startswith(SITE_URL) else None
            if alt and alt not in urls_to_try:
                urls_to_try.append(alt)
        for target_url in urls_to_try:
            for attempt in range(retries):
                try:
                    with urllib.request.urlopen(
                        urllib.request.Request(
                            target_url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                "Referer": SITE_URL,
                                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                "Accept-Language": "en-US,en;q=0.5",
                            },
                        ),
                        timeout=20,
                    ) as response:
                        if response.status == 429:
                            time.sleep(2 ** attempt)
                            continue
                        html = response.read().decode("utf-8", errors="replace")
                        if self._is_cloudflare_challenge(html, response.status):
                            raise ComickApiError(
                                "Comick está com proteção Cloudflare ativa. Tente novamente mais tarde ou use MangaDex. "
                                "(Cloudflare Turnstile bloqueou o acesso sem navegador)"
                            )
                        return html
                except ComickApiError:
                    raise
                except urllib.error.HTTPError as error:
                    body = ""
                    try:
                        body = error.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    if self._is_cloudflare_challenge(body, error.code):
                        raise ComickApiError(
                            "Comick está com proteção Cloudflare ativa. Tente novamente mais tarde ou use MangaDex."
                        ) from error
                    if error.code == 429:
                        time.sleep(2 ** attempt)
                        last_err = error
                        continue
                    last_err = error
                    break
                except (OSError, UnicodeDecodeError) as error:
                    last_err = error
                    time.sleep(0.5 * (attempt + 1))
            if last_err and isinstance(last_err, ComickApiError):
                raise last_err
        if last_err:
            raise ComickApiError(f"Falha ao acessar {url} após {retries} tentativas: {last_err}") from last_err
        raise ComickApiError(f"Falha ao acessar {url}")

    def get_manga(self, comic_hid: str) -> MangaDetails:
        # para slugs do comickz/live (ex: your-mom-is-the-best) tenta html primeiro
        if "-" in comic_hid or len(comic_hid) > 15:
            for base in ["https://comick.live", "https://comickz.co.uk", "https://comick.io", "https://comick.dev"]:
                try:
                    html = self._fetch_html_with_retry(f"{base}/comic/{comic_hid}")
                    m = re.search(r'<script[^>]*id="comic-data"[^>]*>(.+?)</script>', html, re.DOTALL)
                    if m:
                        comic_data = json.loads(m.group(1).strip())
                        return self._parse_comic_data(comic_data, comic_hid)
                except Exception:
                    continue
        try:
            last_err: Exception | None = None
            for base in API_BASE_URLS:
                try:
                    url = f"{base}/comic/{comic_hid}"
                    with urllib.request.urlopen(
                        urllib.request.Request(
                            url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                "Referer": SITE_URL,
                                "Accept": "application/json",
                            },
                        ),
                        timeout=20,
                    ) as response:
                        raw = response.read().decode("utf-8", errors="replace")
                        if self._is_cloudflare_challenge(raw, response.status):
                            raise ComickApiError(
                                "Comick está com proteção Cloudflare ativa. Tente MangaDex."
                            )
                        data = json.loads(raw)
                    comic_data = data.get("comic", {})
                    if not comic_data:
                        raise ComickApiError("Dados do mangá não encontrados na resposta da API.")
                    return self._parse_comic_data(comic_data, comic_hid)
                except ComickApiError:
                    raise
                except urllib.error.HTTPError as error:
                    body = ""
                    try:
                        body = error.read().decode("utf-8", errors="replace")
                    except Exception:
                        pass
                    if self._is_cloudflare_challenge(body, error.code):
                        raise ComickApiError(
                            "Comick está com proteção Cloudflare ativa. Tente MangaDex."
                        ) from error
                    last_err = error
                    continue
                except Exception as error:
                    last_err = error
                    continue
            if last_err:
                raise last_err
        except ComickApiError:
            raise
        except Exception:
            # tenta todos os sites (incluindo comickz.co.uk que usa id="comic-data")
            html = None
            last_html_err = None
            for base in SITE_URLS:
                try:
                    html = self._fetch_html_with_retry(f"{base}/comic/{comic_hid}")
                    break
                except Exception as e:
                    last_html_err = e
                    continue
            if html is None:
                raise ComickApiError(f"Nao encontrou dados do mangá na página: {last_html_err}") from last_html_err
            # comickz usa id="comic-data", comick.io usa __NEXT_DATA__
            match = re.search(r'<script[^>]*id="comic-data"[^>]*>(.+?)</script>', html, re.DOTALL)
            if match:
                try:
                    comic_data = json.loads(match.group(1).strip())
                    # html embed already is the comic object
                    return self._parse_comic_data(comic_data, comic_hid)
                except (json.JSONDecodeError, KeyError) as error:
                    raise ComickApiError(f"Falha ao processar dados do mangá: {error}") from error
            match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
            if not match:
                raise ComickApiError("Nao encontrou dados do mangá na página.")
            try:
                data = json.loads(match.group(1))
                comic_data = data["props"]["pageProps"]["comic"]
            except (json.JSONDecodeError, KeyError) as error:
                raise ComickApiError(f"Falha ao processar dados do mangá: {error}") from error
            return self._parse_comic_data(comic_data, comic_hid)

    def get_manga_chapters(self, comic_hid: str) -> list[ChapterGroup]:
        # para comickz, comic_hid pode ser hid (QxMYyht) mas a API precisa do slug
        slug_to_try = comic_hid
        if comic_hid in self._chapter_map:
            slug_to_try = self._chapter_map[comic_hid][0]
        elif self._last_slug and ("-" not in comic_hid and len(comic_hid) < 12):
            slug_to_try = self._last_slug
        # tenta primeiro estilo comickz/live (slug) - https://comickz.co.uk/api/comics/{slug}/chapter-list
        # tenta slug_to_try primeiro, depois comic_hid
        for slug in ([slug_to_try, comic_hid] if slug_to_try != comic_hid else [comic_hid]):
            for site in SITE_URLS:
                if "comickz" in site or "comick.live" in site:
                    try:
                        return self._get_chapters_comickz(site, slug)
                    except Exception:
                        continue
        chapters: list[ChapterGroup] = []
        page = 1
        try:
            while True:
                url = f"{API_BASE_URL}/comic/{comic_hid}/chapters?page={page}&limit=100"
                try:
                    with urllib.request.urlopen(
                        urllib.request.Request(
                            url,
                            headers={
                                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                "Referer": SITE_URL,
                                "Accept": "application/json",
                                "Accept-Language": "en-US,en;q=0.9",
                            },
                        ),
                        timeout=20,
                    ) as response:
                        data = json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as error:
                    if error.code == 404:
                        url = f"{API_BASE_URL}/chapter?comic_id={comic_hid}&page={page}&limit=100"
                        try:
                            with urllib.request.urlopen(
                                urllib.request.Request(
                                    url,
                                    headers={
                                        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                        "Referer": SITE_URL,
                                        "Accept": "application/json",
                                    },
                                ),
                                timeout=20,
                            ) as response:
                                data = json.loads(response.read().decode("utf-8"))
                        except Exception:
                            raise ComickApiError(f"Erro HTTP {error.code} ao buscar capítulos") from error
                    else:
                        raise
                except (OSError, json.JSONDecodeError) as error:
                    raise ComickApiError(f"Falha ao buscar capítulos: {error}") from error
                chapter_list = data if isinstance(data, list) else data.get("chapters", [])
                if not chapter_list:
                    break
                for ch in chapter_list:
                    volume = ch.get("vol") or "Sem volume"
                    chapter_num = ch.get("chap") or "Extra"
                    title = ch.get("title") or ""
                    lang = ch.get("lang") or "unknown"
                    group_name = ch.get("group_name") or []
                    chapters.append(
                        ChapterGroup(
                            id=ch.get("hid", ""),
                            volume=str(volume),
                            chapter=str(chapter_num),
                            title=str(title),
                            languages=[lang],
                            groups=group_name if isinstance(group_name, list) else [group_name],
                            updated_at=ch.get("updated_at"),
                        )
                    )
                page += 1
                if len(chapter_list) < 100:
                    break
                time.sleep(0.2)
            chapters.sort(key=lambda item: self._sort_number(item.chapter), reverse=True)
            return chapters
        except Exception:
            return self._get_chapters_from_html(comic_hid)

    def _get_chapters_comickz(self, site: str, slug: str) -> list[ChapterGroup]:
        chapters: list[ChapterGroup] = []
        page = 1
        while True:
            url = f"{site}/api/comics/{slug}/chapter-list?page={page}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": site, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                if self._is_cloudflare_challenge(raw, resp.status):
                    raise ComickApiError("Cloudflare block")
                data = json.loads(raw)
            # comickz retorna {"data":[...], "pagination":...} ou {"data":{...}}
            chapter_list = data.get("data") if isinstance(data, dict) else data
            if isinstance(chapter_list, dict):
                chapter_list = chapter_list.get("data", [])
            if not chapter_list:
                # também tenta chave chapters
                chapter_list = data.get("chapters", []) if isinstance(data, dict) else []
            if not chapter_list:
                break
            for ch in chapter_list:
                hid = ch.get("hid", "")
                chap = str(ch.get("chap") or "Extra")
                lang = ch.get("lang") or "unknown"
                chapters.append(
                    ChapterGroup(
                        id=hid,
                        volume=str(ch.get("vol") or "Sem volume"),
                        chapter=chap,
                        title=str(ch.get("title") or ""),
                        languages=[lang],
                        groups=ch.get("group_name") if isinstance(ch.get("group_name"), list) else [ch.get("group_name") or ""],
                        updated_at=ch.get("updated_at") or ch.get("created_at"),
                    )
                )
                if hid:
                    self._chapter_map[hid] = (slug, chap, lang)
            pagination = data.get("pagination", {}) if isinstance(data, dict) else {}
            if pagination.get("last_page") and page >= pagination.get("last_page", 1):
                break
            if len(chapter_list) < 60:
                break
            page += 1
            time.sleep(0.2)
        if not chapters:
            raise ComickApiError("Nenhum capítulo via comickz api")
        chapters.sort(key=lambda x: self._sort_number(x.chapter), reverse=True)
        # guarda slug para páginas
        self._last_slug = slug
        self._last_site = site
        return chapters

    def _get_chapters_from_html(self, comic_hid: str) -> list[ChapterGroup]:
        # tenta comickz primeiro via comic-data firstChapters
        for base in SITE_URLS:
            try:
                html = self._fetch_html_with_retry(f"{base}/comic/{comic_hid}")
                # comickz
                m = re.search(r'<script[^>]*id="comic-data"[^>]*>(.+?)</script>', html, re.DOTALL)
                if m:
                    data = json.loads(m.group(1).strip())
                    chapters_data = data.get("firstChapters") or []
                    if chapters_data:
                        chapters: list[ChapterGroup] = []
                        for ch in chapters_data:
                            chapters.append(
                                ChapterGroup(
                                    id=ch.get("hid", ""),
                                    volume=str(ch.get("vol") or "Sem volume"),
                                    chapter=str(ch.get("chap") or "Extra"),
                                    title=str(ch.get("title") or ""),
                                    languages=[ch.get("lang") or "unknown"],
                                    groups=ch.get("group_name") if isinstance(ch.get("group_name"), list) else [ch.get("group_name") or ""],
                                    updated_at=ch.get("updated_at") or ch.get("created_at"),
                                )
                            )
                        chapters.sort(key=lambda x: self._sort_number(x.chapter), reverse=True)
                        self._last_slug = data.get("slug", comic_hid)
                        self._last_site = base
                        return chapters
                match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
                if match:
                    data = json.loads(match.group(1))
                    chapters_data = data["props"]["pageProps"].get("firstChapters") or data["props"]["pageProps"].get("chapters", [])
                    if chapters_data:
                        chapters: list[ChapterGroup] = []
                        for ch in chapters_data:
                            chapters.append(
                                ChapterGroup(
                                    id=ch.get("hid", ""),
                                    volume=str(ch.get("vol") or "Sem volume"),
                                    chapter=str(ch.get("chap") or "Extra"),
                                    title=str(ch.get("title") or ""),
                                    languages=[ch.get("lang") or "unknown"],
                                    groups=ch.get("group_name") if isinstance(ch.get("group_name"), list) else [ch.get("group_name") or ""],
                                    updated_at=ch.get("updated_at"),
                                )
                            )
                        chapters.sort(key=lambda x: self._sort_number(x.chapter), reverse=True)
                        return chapters
            except Exception:
                continue
        html = self._fetch_html_with_retry(f"{SITE_URL}/comic/{comic_hid}")
        match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>', html)
        if not match:
            raise ComickApiError("Nao encontrou dados do mangá na página.")
        try:
            data = json.loads(match.group(1))
            chapters_data = data["props"]["pageProps"].get("firstChapters") or data["props"]["pageProps"].get("chapters", [])
        except (json.JSONDecodeError, KeyError) as error:
            raise ComickApiError(f"Falha ao processar dados dos capítulos: {error}") from error
        chapters: list[ChapterGroup] = []
        for ch in chapters_data:
            volume = ch.get("vol") or "Sem volume"
            chapter_num = ch.get("chap") or "Extra"
            title = ch.get("title") or ""
            lang = ch.get("lang") or "unknown"
            group_name = ch.get("group_name") or []
            chapters.append(
                ChapterGroup(
                    id=ch.get("hid", ""),
                    volume=str(volume),
                    chapter=str(chapter_num),
                    title=str(title),
                    languages=[lang],
                    groups=group_name if isinstance(group_name, list) else [group_name],
                    updated_at=ch.get("updated_at"),
                )
            )
        chapters.sort(key=lambda item: self._sort_number(item.chapter), reverse=True)
        return chapters

    def get_chapter_pages(self, chapter_hid: str) -> ChapterPages:
        # tenta comickz via HTML (cdn1.comicknew.pictures)
        if chapter_hid in self._chapter_map or self._last_slug:
            info = self._chapter_map.get(chapter_hid)
            if info:
                slug, chap, lang = info
                site = self._last_site or "https://comickz.co.uk"
                for base in [site, "https://comickz.co.uk", "https://comick.io"]:
                    for url in [
                        f"{base}/comic/{slug}/{chapter_hid}-chapter-{chap}-{lang}",
                        f"{base}/comic/{slug}/{chapter_hid}",
                    ]:
                        try:
                            html = self._fetch_html_with_retry(url)
                            # comickz chapter images estão em json com "images":[{"url":...}]
                            m = re.search(r'"images"\s*:\s*\[(.*?)\]', html, re.DOTALL)
                            if m:
                                urls = re.findall(r'"url"\s*:\s*"([^"]+)"', m.group(1))
                                # filtra apenas urls de imagem
                                pages = [u.replace("\\/", "/") for u in urls if "comick" in u or u.startswith("http")]
                                if pages:
                                    return ChapterPages(chapter_id=chapter_hid, hash=chapter_hid, pages=pages)
                            # fallback: procura cdn1
                            urls = re.findall(r'https://cdn1\.comicknew\.pictures[^"]+', html)
                            if urls:
                                pages = [u.replace("\\/", "/") for u in urls]
                                # remove duplicatas mantendo ordem
                                seen = set()
                                uniq = []
                                for p in pages:
                                    if p not in seen:
                                        seen.add(p)
                                        uniq.append(p)
                                if uniq:
                                    return ChapterPages(chapter_id=chapter_hid, hash=chapter_hid, pages=uniq)
                        except Exception:
                            continue
        # fallback para api antiga (comick.io)
        url = f"{API_BASE_URL}/chapter/{chapter_hid}"
        try:
            with urllib.request.urlopen(
                urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0",
                        "Referer": SITE_URL,
                    },
                ),
                timeout=20,
            ) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise ComickApiError(f"Erro HTTP {error.code} ao buscar páginas") from error
        except (OSError, json.JSONDecodeError) as error:
            raise ComickApiError(f"Falha ao buscar páginas: {error}") from error
        chapter_data = data.get("chapter", {})
        md_images = chapter_data.get("md_images", [])
        if not md_images:
            raise ComickApiError("Nao encontrou páginas para esse capítulo.")
        pages = [f"{IMAGE_BASE_URL}/{img.get('b2key', '')}" for img in md_images if img.get("b2key")]
        return ChapterPages(chapter_id=chapter_hid, hash=chapter_hid, pages=pages)

    def _sort_number(self, value: str) -> float:
        try:
            return float(value)
        except ValueError:
            return -1.0

    def parse_comick_url(self, url: str) -> tuple[str, str]:
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc.lower() not in {"comick.io", "comick.app", "comick.cc", "comick.ink", "comick.dev", "comickz.co.uk", "comickz.cc", "comickz.app", "comick.live"}:
            raise ComickApiError("Use uma URL do comick.io / comickz.co.uk / comick.live.")
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) < 2:
            raise ComickApiError("URL do Comick incompleta.")
        resource_type = parts[0]
        resource_id = parts[1]
        if resource_type != "comic":
            raise ComickApiError("Por enquanto aceito apenas URL de comic.")
        return resource_type, resource_id
