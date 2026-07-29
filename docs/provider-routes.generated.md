# Provider 路由清单（自动生成）

本文件由 `scripts/check_provider_governance.py --update` 从运行时 `ProviderSpec.routes` 生成，请勿手工编辑。

| Provider | 顺序 | Route | Kind / Source | 状态 / Runtime | 限制 | Acceptance / Assets |
| --- | ---: | --- | --- | --- | --- | --- |
| `crossref` | 0 | `metadata` | `metadata` / `crossref_meta` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `none` |
| `elsevier` | 0 | `metadata_api` | `metadata` / `metadata_api` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `none` |
| `elsevier` | 1 | `xml_api` | `xml` / `elsevier_xml` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `structured_xml_body` / `none` |
| `elsevier` | 2 | `pdf_api` | `pdf` / `elsevier_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `none` |
| `elsevier` | 3 | `object_assets` | `assets` / `elsevier_xml` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `validated_asset` / `none` |
| `springer` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `springer` | 1 | `direct_html` | `html` / `springer_html` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `springer` | 2 | `direct_pdf` | `pdf` / `springer_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `wiley` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `wiley` | 1 | `browser_html` | `html` / `wiley_browser` | `available` / `browser-optional` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `wiley` | 2 | `tdm_pdf` | `pdf` / `wiley_browser` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `wiley` | 3 | `browser_pdf` | `pdf` / `wiley_browser` | `available` / `browser-optional` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `science` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `science` | 1 | `browser_html` | `html` / `science` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `science` | 2 | `browser_pdf` | `pdf` / `science` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `pnas` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `pnas` | 1 | `browser_html` | `html` / `pnas` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `pnas` | 2 | `browser_pdf` | `pdf` / `pnas` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `ieee` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `ieee` | 1 | `rest_html` | `html` / `ieee_html` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `ieee` | 2 | `browser_html` | `html` / `ieee_html` | `available` / `browser-optional` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `ieee` | 3 | `direct_pdf` | `pdf` / `ieee_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `ieee` | 4 | `browser_pdf` | `pdf` / `ieee_pdf` | `available` / `browser-optional` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `arxiv` | 0 | `atom_metadata` | `metadata` / `atom_metadata` | `available` / `direct` | 20s; c=2; qps=0.3333333333333333; wait=5.0s | `metadata_identity` / `body` |
| `arxiv` | 1 | `official_html` | `html` / `arxiv_html` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `arxiv` | 2 | `direct_pdf` | `pdf` / `arxiv_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `copernicus` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `copernicus` | 1 | `xml` | `xml` / `copernicus_xml` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `structured_xml_body` / `body` |
| `copernicus` | 2 | `direct_pdf` | `pdf` / `copernicus_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `ams` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `ams` | 1 | `browser_html` | `html` / `ams_html` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `ams` | 2 | `browser_pdf` | `pdf` / `ams_pdf` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `mdpi` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `mdpi` | 1 | `browser_html` | `html` / `mdpi_html` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `mdpi` | 2 | `browser_pdf` | `pdf` / `mdpi_pdf` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `royalsocietypublishing` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `royalsocietypublishing` | 1 | `browser_html` | `html` / `royalsocietypublishing_html` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `royalsocietypublishing` | 2 | `browser_pdf` | `pdf` / `royalsocietypublishing_pdf` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `annualreviews` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `annualreviews` | 1 | `browser_html` | `html` / `annualreviews_html` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `annualreviews` | 2 | `browser_pdf` | `pdf` / `annualreviews_pdf` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `plos` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `plos` | 1 | `xml` | `xml` / `plos_xml` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `structured_xml_body` / `body` |
| `plos` | 2 | `direct_pdf` | `pdf` / `plos_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `oxfordacademic` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `oxfordacademic` | 1 | `direct_html` | `html` / `oxfordacademic_html` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `oxfordacademic` | 2 | `direct_pdf` | `pdf` / `oxfordacademic_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `acs` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `acs` | 1 | `browser_html` | `html` / `acs` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `acs` | 2 | `browser_pdf` | `pdf` / `acs` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `iop` | 0 | `metadata` | `metadata` / `crossref_metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `iop` | 1 | `tdm_xml` | `xml` / `iop_xml` | `unsupported` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `jats_body` / `body` |
| `iop` | 2 | `browser_html` | `html` / `iop_html` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `iop` | 3 | `browser_pdf` | `pdf` / `iop_pdf` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `aip` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `aip` | 1 | `browser_html` | `html` / `aip_html` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `provider_html_body` / `body` |
| `aip` | 2 | `browser_pdf` | `pdf` / `aip_pdf` | `available` / `browser-required` | 120s; c=1; qps=provider; wait=5.0s | `validated_pdf` / `body` |
| `frontiers` | 0 | `metadata` | `metadata` / `metadata` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `metadata_identity` / `body` |
| `frontiers` | 1 | `xml` | `xml` / `frontiers_xml` | `available` / `direct` | 20s; c=2; qps=provider; wait=5.0s | `structured_xml_body` / `body` |
| `frontiers` | 2 | `direct_pdf` | `pdf` / `frontiers_pdf` | `available` / `direct` | 120s; c=2; qps=provider; wait=5.0s | `validated_pdf` / `body` |

机器可读快照见 [`../quality/provider-catalog.json`](../quality/provider-catalog.json)。
