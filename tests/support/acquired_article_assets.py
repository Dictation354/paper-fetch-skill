"""Shared test support; contains no collected tests."""

from paper_fetch.providers import (
    acs,
    aip,
    ams,
    annualreviews,
    iop,
    mdpi,
    pnas,
    science,
    tandf,
    wiley,
)

CLIENTS = {
    "ams": ams.AmsClient,
    "iop": iop.IopClient,
    "pnas": pnas.PnasClient,
    "aip": aip.AipClient,
    "annualreviews": annualreviews.AnnualreviewsClient,
    "science": science.ScienceClient,
    "tandf": tandf.TandfClient,
    "wiley": wiley.WileyClient,
    "acs": acs.AcsClient,
    "mdpi": mdpi.MdpiClient,
}
