"""Servicos internos do app."""

from services.comick_api import ComickApiClient, ComickApiError
from services.mangadex_api import MangaDexApiClient, MangaDexApiError
from services.models import (
    ChapterGroup,
    ChapterGroup as ComickChapterGroup,
    ChapterPages,
    ChapterPages as ComickChapterPages,
    MangaDetails,
    MangaDetails as ComickMangaDetails,
    MangaSummary,
    MangaSummary as ComickMangaSummary,
    MdListDetails,
    UserMdList,
    UserProfile,
)
