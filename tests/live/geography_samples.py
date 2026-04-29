"""Natural-geography live sample catalog for publisher end-to-end checks."""

from __future__ import annotations

from paper_fetch_devtools.geography.live import GEOGRAPHY_PROVIDER_ORDER, GeographySample

GEOGRAPHY_TOPIC_TAGS = (
    "climate",
    "hydrology",
    "precipitation",
    "drought",
    "vegetation",
    "phenology",
    "deforestation",
    "geomorphology",
    "cryosphere",
    "volcano",
    "remote_sensing",
    "land_atmosphere",
)


def _default_landing_url(provider: str, doi: str) -> str:
    if provider == "wiley":
        return f"https://onlinelibrary.wiley.com/doi/full/{doi}"
    if provider == "science":
        return f"https://www.science.org/doi/{doi}"
    if provider == "pnas":
        return f"https://www.pnas.org/doi/full/{doi}"
    return f"https://doi.org/{doi}"


def _sample(
    provider: str,
    doi: str,
    title: str,
    *,
    year: int,
    topic_tags: tuple[str, ...],
    seed_level: int = 1,
    landing_url: str | None = None,
) -> GeographySample:
    return GeographySample(
        provider=provider,
        doi=doi,
        title=title,
        landing_url=landing_url or _default_landing_url(provider, doi),
        topic_tags=topic_tags,
        year=year,
        seed_level=seed_level,
    )


ELSEVIER_GEOGRAPHY_SAMPLES = (
    _sample(
        "elsevier",
        "10.1016/j.rse.2025.114648",
        "Seasonality of vegetation greenness in Southeast Asia unveiled by geostationary satellite observations",
        year=2025,
        topic_tags=("remote_sensing", "vegetation", "climate", "phenology"),
        seed_level=2,
        landing_url="https://linkinghub.elsevier.com/retrieve/pii/S0034425725000525",
    ),
    _sample(
        "elsevier",
        "10.1016/j.jhydrol.2021.126210",
        "The interactions between hydrological drought evolution and precipitation-streamflow relationship",
        year=2021,
        topic_tags=("hydrology", "drought", "precipitation"),
        seed_level=2,
        landing_url="https://linkinghub.elsevier.com/retrieve/pii/S0022169421002572",
    ),
    _sample(
        "elsevier",
        "10.1016/j.jhydrol.2023.130125",
        "An evaluation of the response of vegetation greenness, moisture, fluorescence, and temperature-based remote sensing indicators to drought stress",
        year=2023,
        topic_tags=("drought", "vegetation", "remote_sensing"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.scitotenv.2022.158109",
        "Land-atmosphere coupling speeds up flash drought onset",
        year=2022,
        topic_tags=("land_atmosphere", "drought", "climate"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.scitotenv.2022.158499",
        "Assessing the impact of drought-land cover change on global vegetation greenness and productivity",
        year=2022,
        topic_tags=("drought", "vegetation", "climate"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.rse.2024.114346",
        "Patterns and Trends in Northern Hemisphere River Ice Phenology from 2000 to 2021",
        year=2024,
        topic_tags=("cryosphere", "hydrology", "phenology", "remote_sensing"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.ecolind.2023.110326",
        "Climate warming-induced phenology changes dominate vegetation productivity in Northern Hemisphere ecosystems",
        year=2023,
        topic_tags=("climate", "phenology", "vegetation"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.ecolind.2024.112140",
        "The variability in sensitivity of vegetation greenness to climate change across Eurasia",
        year=2024,
        topic_tags=("vegetation", "climate", "remote_sensing"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.agrformet.2024.109975",
        "Optimal representation of spring phenology on photosynthetic productivity across the northern hemisphere forests",
        year=2024,
        topic_tags=("phenology", "vegetation", "climate"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.agrformet.2024.110321",
        "Land-atmosphere feedback exacerbated the mega heatwave and drought over the Yangtze River Basin of China during summer 2022",
        year=2025,
        topic_tags=("land_atmosphere", "drought", "climate"),
    ),
    _sample(
        "elsevier",
        "10.1016/j.jhydrol.2024.132225",
        "Land-atmosphere and ocean-atmosphere couplings dominate the dynamics of agricultural drought predictability in the Loess Plateau, China",
        year=2024,
        topic_tags=("land_atmosphere", "hydrology", "drought"),
        seed_level=0,
    ),
    _sample(
        "elsevier",
        "10.1016/j.catena.2024.108542",
        "Vegetation vulnerability in karst desertification areas is related to land-atmosphere feedback induced by lithology",
        year=2024,
        topic_tags=("vegetation", "land_atmosphere", "geomorphology"),
        seed_level=0,
    ),
)

SPRINGER_GEOGRAPHY_SAMPLES = (
    _sample(
        "springer",
        "10.1038/s41561-022-00983-6",
        "Ozone depletion over the Arctic affects spring climate in the Northern Hemisphere",
        year=2022,
        topic_tags=("climate", "precipitation", "cryosphere"),
        seed_level=2,
        landing_url="https://www.nature.com/articles/s41561-022-00983-6",
    ),
    _sample(
        "springer",
        "10.1038/s41561-022-00974-7",
        "Springtime arctic ozone depletion forces northern hemisphere climate anomalies",
        year=2022,
        topic_tags=("climate", "precipitation", "cryosphere"),
        seed_level=2,
        landing_url="https://www.nature.com/articles/s41561-022-00974-7",
    ),
    _sample(
        "springer",
        "10.1038/s43247-024-01295-w",
        "Hydrological drought forecasts using precipitation data depend on catchment properties and human activities",
        year=2024,
        topic_tags=("hydrology", "drought", "precipitation"),
    ),
    _sample(
        "springer",
        "10.1038/s44221-022-00024-x",
        "How Australia's Millennium drought induced hydrological shifts",
        year=2023,
        topic_tags=("hydrology", "drought", "climate"),
    ),
    _sample(
        "springer",
        "10.1038/s41467-022-30729-2",
        "The timing of unprecedented hydrological drought under climate change",
        year=2022,
        topic_tags=("hydrology", "drought", "climate"),
    ),
    _sample(
        "springer",
        "10.1038/s41558-022-01584-2",
        "Widespread spring phenology effects on drought recovery of Northern Hemisphere ecosystems",
        year=2023,
        topic_tags=("phenology", "drought", "vegetation", "climate"),
    ),
    _sample(
        "springer",
        "10.1038/s43247-024-01270-5",
        "Earlier spring greening in Northern Hemisphere terrestrial biomes enhanced net ecosystem productivity in summer",
        year=2024,
        topic_tags=("phenology", "vegetation", "climate"),
    ),
    _sample(
        "springer",
        "10.1038/s41612-021-00218-2",
        "Northern Hemisphere drought risk in a warming climate",
        year=2021,
        topic_tags=("drought", "climate", "precipitation"),
    ),
    _sample(
        "springer",
        "10.1038/s41561-022-00912-7",
        "Drought self-propagation in drylands due to land-atmosphere feedbacks",
        year=2022,
        topic_tags=("drought", "land_atmosphere", "climate"),
    ),
    _sample(
        "springer",
        "10.1038/s43247-024-01885-8",
        "Embedding machine-learnt sub-grid variability improves climate model precipitation patterns",
        year=2024,
        topic_tags=("climate", "precipitation"),
    ),
    _sample(
        "springer",
        "10.1038/s43247-024-01544-y",
        "Heterogeneous changes in global glacial lakes under coupled climate warming and glacier thinning",
        year=2024,
        topic_tags=("cryosphere", "climate", "hydrology"),
        seed_level=0,
    ),
    _sample(
        "springer",
        "10.1038/s43247-024-01299-6",
        "Climate and land use changes explain variation in the A horizon and soil thickness in the United States",
        year=2024,
        topic_tags=("climate", "geomorphology", "land_atmosphere"),
        seed_level=0,
    ),
)

WILEY_GEOGRAPHY_SAMPLES = (
    _sample(
        "wiley",
        "10.1111/gcb.16414",
        "Contrasting temperature effects on the velocity of early- versus late-stage vegetation green-up in the Northern Hemisphere",
        year=2022,
        topic_tags=("vegetation", "phenology", "climate"),
        seed_level=2,
        landing_url="https://onlinelibrary.wiley.com/doi/full/10.1111/gcb.16414",
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16561",
        "Climate-driven vegetation greening further reduces water availability in drylands",
        year=2023,
        topic_tags=("vegetation", "climate", "drought", "hydrology"),
        seed_level=2,
        landing_url="https://onlinelibrary.wiley.com/doi/10.1111/gcb.16561",
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16011",
        "Vegetation green-up date is more sensitive to permafrost degradation than climate change in spring across the northern permafrost region",
        year=2022,
        topic_tags=("vegetation", "phenology", "cryosphere", "climate"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.15322",
        "Accelerated rate of vegetation green-up related to warming at northern high latitudes",
        year=2020,
        topic_tags=("vegetation", "phenology", "climate"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16386",
        "Cerrado deforestation threatens regional climate and water availability for agriculture and ecosystems",
        year=2022,
        topic_tags=("deforestation", "climate", "hydrology"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16745",
        "Contrasting ecosystem vegetation response in global drylands under drying and wetting conditions",
        year=2023,
        topic_tags=("vegetation", "drought", "climate"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16455",
        "Tropical surface temperature response to vegetation cover changes and the role of drylands",
        year=2023,
        topic_tags=("vegetation", "climate", "land_atmosphere"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.17141",
        "Declining coupling between vegetation and drought over the past three decades",
        year=2024,
        topic_tags=("vegetation", "drought", "climate"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16998",
        "Drought thresholds that impact vegetation reveal the divergent responses of vegetation growth to drought across China",
        year=2024,
        topic_tags=("vegetation", "drought", "climate"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16758",
        "Spring phenology rather than climate dominates the trends in peak of growing season in the Northern Hemisphere",
        year=2023,
        topic_tags=("phenology", "vegetation", "climate"),
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16543",
        "A critical thermal transition driving spring phenology of Northern Hemisphere conifers",
        year=2023,
        topic_tags=("phenology", "vegetation", "climate"),
        seed_level=0,
    ),
    _sample(
        "wiley",
        "10.1111/gcb.16580",
        "Satellite observed reversal in trends of spring phenology in the middle-high latitudes of the Northern Hemisphere during the global warming hiatus",
        year=2023,
        topic_tags=("phenology", "vegetation", "climate", "remote_sensing"),
        seed_level=0,
    ),
)

SCIENCE_GEOGRAPHY_SAMPLES = (
    _sample(
        "science",
        "10.1126/science.aeg3511",
        "Magma plumbing beneath Yellowstone",
        year=2026,
        topic_tags=("volcano", "geomorphology", "climate"),
        seed_level=2,
        landing_url="https://www.science.org/doi/10.1126/science.aeg3511",
    ),
    _sample(
        "science",
        "10.1126/science.adp0212",
        "Anthropogenic amplification of precipitation variability over the past century",
        year=2024,
        topic_tags=("precipitation", "climate", "hydrology"),
        seed_level=2,
        landing_url="https://www.science.org/doi/full/10.1126/science.adp0212",
    ),
    _sample(
        "science",
        "10.1126/science.ade0347",
        "Magma accumulation at depths of prior rhyolite storage beneath Yellowstone Caldera",
        year=2022,
        topic_tags=("volcano", "geomorphology"),
    ),
    _sample(
        "science",
        "10.1126/science.abp8622",
        "The drivers and impacts of Amazon forest degradation",
        year=2023,
        topic_tags=("deforestation", "climate", "vegetation"),
    ),
    _sample(
        "science",
        "10.1126/science.abb3021",
        "Long-term forest degradation surpasses deforestation in the Brazilian Amazon",
        year=2020,
        topic_tags=("deforestation", "climate", "vegetation"),
    ),
    _sample(
        "science",
        "10.1126/sciadv.abj3309",
        "Projections of future forest degradation and CO2 emissions for the Brazilian Amazon",
        year=2022,
        topic_tags=("deforestation", "climate", "vegetation"),
    ),
    _sample(
        "science",
        "10.1126/sciadv.adm9732",
        "Disturbance amplifies sensitivity of dryland productivity to precipitation variability",
        year=2024,
        topic_tags=("precipitation", "drought", "vegetation"),
    ),
    _sample(
        "science",
        "10.1126/sciadv.aax6869",
        "Strong future increases in Arctic precipitation variability linked to poleward moisture transport",
        year=2020,
        topic_tags=("precipitation", "climate", "cryosphere"),
    ),
    _sample(
        "science",
        "10.1126/sciadv.abf8021",
        "Increasing precipitation variability on daily-to-multiyear time scales in a warmer world",
        year=2021,
        topic_tags=("precipitation", "climate"),
    ),
    _sample(
        "science",
        "10.1126/sciadv.abg9690",
        "Greenhouse warming intensifies north tropical Atlantic climate variability",
        year=2021,
        topic_tags=("climate", "precipitation"),
    ),
    _sample(
        "science",
        "10.1126/science.adi1071",
        "Drought sensitivity in mesic forests heightens their vulnerability to climate change",
        year=2023,
        topic_tags=("drought", "vegetation", "climate"),
        seed_level=0,
    ),
    _sample(
        "science",
        "10.1126/science.adr6700",
        "Coupled, decoupled, and abrupt responses of vegetation to climate across timescales",
        year=2025,
        topic_tags=("vegetation", "climate"),
        seed_level=0,
    ),
)

PNAS_GEOGRAPHY_SAMPLES = (
    _sample(
        "pnas",
        "10.1073/pnas.2309123120",
        "Amazon deforestation causes strong regional warming",
        year=2023,
        topic_tags=("deforestation", "climate", "land_atmosphere"),
        seed_level=2,
        landing_url="https://www.pnas.org/doi/full/10.1073/pnas.2309123120",
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2317456120",
        "Amazon deforestation implications in local/regional climate change",
        year=2023,
        topic_tags=("deforestation", "climate", "land_atmosphere"),
        seed_level=2,
        landing_url="https://www.pnas.org/doi/full/10.1073/pnas.2317456120",
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2208095119",
        "The importance of internal climate variability in climate impact projections",
        year=2022,
        topic_tags=("climate", "precipitation"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2310157121",
        "A large net carbon loss attributed to anthropogenic and natural disturbances in the Amazon Arc of Deforestation",
        year=2024,
        topic_tags=("deforestation", "climate", "vegetation"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.1915921117",
        "Global snow drought hot spots and characteristics",
        year=2020,
        topic_tags=("drought", "cryosphere", "hydrology"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2402656121",
        "US Corn Belt enhances regional precipitation recycling",
        year=2025,
        topic_tags=("precipitation", "land_atmosphere", "hydrology"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2410294121",
        "Surging compound drought-heatwaves underrated in global soils",
        year=2024,
        topic_tags=("drought", "climate"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2322622121",
        "Partitioning the drivers of Antarctic glacier mass balance (2003-2020) using satellite observations and a regional climate model",
        year=2024,
        topic_tags=("cryosphere", "climate", "hydrology", "remote_sensing"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2314265121",
        "Weaker land-atmosphere coupling in global storm-resolving simulation",
        year=2024,
        topic_tags=("land_atmosphere", "climate", "precipitation"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2305050120",
        "Dryland sensitivity to climate change and variability using nonlinear dynamics",
        year=2023,
        topic_tags=("drought", "climate", "vegetation"),
    ),
    _sample(
        "pnas",
        "10.1073/pnas.1911015117",
        "Time-evolving sea-surface warming patterns modulate the climate change response of subtropical precipitation over land",
        year=2020,
        topic_tags=("precipitation", "climate"),
        seed_level=0,
    ),
    _sample(
        "pnas",
        "10.1073/pnas.2001403117",
        "Land use and climate change impacts on global soil erosion by water (2015-2070)",
        year=2020,
        topic_tags=("geomorphology", "climate", "hydrology"),
        seed_level=0,
    ),
)

GEOGRAPHY_SAMPLE_CATALOG = {
    "elsevier": ELSEVIER_GEOGRAPHY_SAMPLES,
    "springer": SPRINGER_GEOGRAPHY_SAMPLES,
    "wiley": WILEY_GEOGRAPHY_SAMPLES,
    "science": SCIENCE_GEOGRAPHY_SAMPLES,
    "pnas": PNAS_GEOGRAPHY_SAMPLES,
}


def all_geography_samples() -> tuple[GeographySample, ...]:
    ordered: list[GeographySample] = []
    for provider in GEOGRAPHY_PROVIDER_ORDER:
        ordered.extend(GEOGRAPHY_SAMPLE_CATALOG[provider])
    return tuple(ordered)
