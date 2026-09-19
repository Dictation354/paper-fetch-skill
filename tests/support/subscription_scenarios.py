"""Reviewed response expectations; never derived from the detector under test."""

# Keys identify the historical block response, not every response for that DOI.
# The ac3460 block is a challenge; its later subscription response is separate.
BLOCK_PAYWALLS = {
    "10.1073/pnas.2509692123",
    "10.1073/pnas.2523032123",
    "10.1073/pnas.2534432123",
    "10.1073/pnas.2607267123",
    "10.1126/science.167.3914.61",
    "10.1126/science.6985744",
    "10.1126/science.7809609",
    "10.1146/annurev-neuro-062111-150343",
    "10.1088/0034-4885/53/3/002",
    "10.1088/1681-7575/ae1dfc",
    "10.1093/reseval/rvag052",
    "10.1126/science.aeg3511",
    "10.1007/s11430-021-9892-6",
    "10.1007/s12652-019-01399-8",
    "10.1007/s13351-020-9829-8",
    "10.1038/nature12915",
    "10.1080/01431161.2025.2516689",
}
BLOCK_NOT_PAYWALLS = {
    "10.1063/5.0129134",  # historical challenge DOM; HTTP status unknown
    "10.1175/jamc-d-24-0048.1",  # CloudFront refusal, no entitlement evidence
    "10.1146/annurev.pp.19.060168.001235",
    "10.1088/2058-9565/ac3460",  # historical human-verification page
    "10.3390/math11030657",
    "10.1093/bioinformatics/btaa823",  # historical challenge DOM
    "10.1007/s00382-018-4286-0",
    "10.1080/17538947.2022.2137254",
    "10.1111/gcb.16386",
    "10.1111/gcb.16414",
    "10.1111/gcb.16758",
    "10.1111/gcb.16998",
}

# Actual HTTP entities from the subscription collection, reviewed independently.
# JAS has purchase-only access; JPO has a readable body. Science/PNAS put
# an explicit denial block in bodymatter. Wiley only exposes an abstract page.
SUBSCRIPTION_RESPONSES = (
    # Same JAS DOI later returned a readable body: retain both response histories.
    (
        "ams",
        "10.1175/jas-d-26-0015.1",
        "acquisition/pdf-identity-recheck-2026-09-15/response-001.bin",
        False,
    ),
    (
        "ams",
        "10.1175/jas-d-26-0015.1",
        "acquisition/pdf-identity-recheck-2026-09-15/response-002.bin",
        False,
    ),
    ("iop", "10.1088/1681-7575/ae1dfc", "response-001.bin", True),
    ("iop", "10.1088/0034-4885/53/3/002", "response-001.bin", True),
    ("iop", "10.1088/2058-9565/ac3460", "response-001.bin", True),
    ("acs", "10.1021/ja00160a040", "response-003.bin", True),
    ("acs", "10.1021/jacs.6c10062", "response-003.bin", True),
    ("aip", "10.1063/1.39658", "response-003.bin", True),
    ("aip", "10.1063/5.0260731", "response-003.bin", True),
    ("royalsocietypublishing", "10.1098/rspa.1984.0023", "response-001.bin", True),
    ("ams", "10.1175/jas-d-26-0015.1", "response-001.bin", True),
    ("ams", "10.1175/jpo-d-24-0098.1", "response-001.bin", False),
    ("science", "10.1126/science.aeg3511", "response-003.bin", True),
    ("science", "10.1126/science.7809609", "response-002.bin", True),
    ("pnas", "10.1073/pnas.2509692123", "response-002.bin", True),
    ("pnas", "10.1073/pnas.2607267123", "response-002.bin", True),
    ("wiley", "10.1111/gcb.16758", "response-003.bin", False),
    ("wiley", "10.1111/gcb.16998", "response-006.bin", False),
)
