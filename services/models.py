"""Modelos compartilhados entre MangaDex e Comick."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MangaSummary:
    id: str
    title: str
    cover_url: str | None


@dataclass(frozen=True)
class MangaDetails(MangaSummary):
    description: str
    tags: list[str] | None = None
    year: int | None = None
    status: str | None = None
    descriptions: dict[str, str] | None = None


@dataclass(frozen=True)
class ChapterGroup:
    id: str
    volume: str
    chapter: str
    title: str
    languages: list[str]
    groups: list[str]
    updated_at: str | None


@dataclass(frozen=True)
class ChapterPages:
    chapter_id: str
    hash: str
    pages: list[str]


@dataclass(frozen=True)
class MdListDetails:
    id: str
    name: str
    manga: list[MangaSummary]


@dataclass(frozen=True)
class UserProfile:
    id: str
    username: str
    avatar_url: str | None
    banner_url: str | None


@dataclass(frozen=True)
class UserMdList:
    id: str
    name: str
    visibility: str
    manga: list[MangaSummary]
    source: str = "mine"
