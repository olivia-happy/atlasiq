from __future__ import annotations

from ..schemas import CountryProfile, CountryWorkspace


COUNTRY_PROFILES: tuple[CountryProfile, ...] = (
    CountryProfile(
        id="de",
        name="Germany",
        display_name="德国",
        market_label="德国光伏市场",
        market_pack_id="de-pv",
        latitude=51.1657,
        longitude=10.4515,
        timezone="Europe/Berlin",
        news_query="Germany solar photovoltaic grid",
    ),
    CountryProfile(
        id="es",
        name="Spain",
        display_name="西班牙",
        market_label="西班牙光伏市场",
        market_pack_id="es-pv",
        latitude=40.4637,
        longitude=-3.7492,
        timezone="Europe/Madrid",
        news_query="Spain solar photovoltaic grid",
    ),
    CountryProfile(
        id="fr",
        name="France",
        display_name="法国",
        market_label="法国光伏市场",
        market_pack_id="fr-pv",
        latitude=46.2276,
        longitude=2.2137,
        timezone="Europe/Paris",
        news_query="France solar photovoltaic grid",
    ),
    CountryProfile(
        id="ae",
        name="United Arab Emirates",
        display_name="阿联酋",
        market_label="阿联酋光伏市场",
        market_pack_id="ae-pv",
        latitude=23.4241,
        longitude=53.8478,
        timezone="Asia/Dubai",
        news_query="United Arab Emirates solar photovoltaic grid",
    ),
    CountryProfile(
        id="sa",
        name="Saudi Arabia",
        display_name="沙特阿拉伯",
        market_label="沙特阿拉伯光伏市场",
        market_pack_id="sa-pv",
        latitude=23.8859,
        longitude=45.0792,
        timezone="Asia/Riyadh",
        news_query="Saudi Arabia solar photovoltaic grid",
    ),
)


def list_country_profiles() -> list[CountryProfile]:
    return list(COUNTRY_PROFILES)


def get_country_profile(profile_id: str) -> CountryProfile | None:
    return next((profile for profile in COUNTRY_PROFILES if profile.id == profile_id), None)


def get_country_workspace(profile_id: str) -> CountryWorkspace | None:
    profile = get_country_profile(profile_id)
    if profile is None:
        return None

    from .market import get_overview
    from .market_packs import active_pack_version, get_market_pack_version
    from .news import list_news
    from .factors import build_factor_snapshot, get_impact_matrix
    from .feature_store import list_evidence
    from .sources import list_public_sources

    version = active_pack_version(profile.market_pack_id)
    market_pack = get_market_pack_version(profile.market_pack_id, version)
    if market_pack is None:
        return None
    return CountryWorkspace(
        profile=profile,
        market_pack=market_pack,
        overview=get_overview(profile.id),
        sources=list_public_sources(profile.id),
        news=list_news(profile.id),
        features=build_factor_snapshot(profile.id),
        impact_matrix=get_impact_matrix(profile.id),
        evidence_timeline=list_evidence(profile.id),
    )
