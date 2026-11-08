# Source connectors and licensing

Clients use public HTTP endpoints with a 25-second timeout, rate-limited requests, up to four attempts for transient network/429/5xx errors, exponential waits, and a 24-hour timestamp-preserving local cache. They retain source URL, retrieval time, license notes and unmodified source payload. Cache records do not imply licensing permission or scientific endorsement. Lookup pages are bounded to 25 results where supported.

| Client | Implemented lookup | Pagination limitation |
|---|---|---|
| Europe PMC | Search with core publication metadata | Offset page |
| PubMed | ESearch IDs | retstart offset; EFetch metadata not implemented |
| ChEMBL | Molecule search | limit/offset |
| PubChem | Compound-name property lookup | Single-record operation |
| Open Targets | GraphQL entity search | Pagination object |
| UniProt | Protein search | First page only; cursor handling not implemented |
| Reactome | Content service search | Start row/rows |
| STRING | Human interaction lookup | Bounded single operation |
| openFDA | Exact generic-name label search | limit/skip, 5 records per page |

Response validation checks JSON container types and source error fields; Europe PMC additionally validates its result-list shape. Full source-specific record schemas are not implemented for every connector. API schema drift may produce an explicit error or require adapter updates. Tests use mock HTTP transport; live endpoints are not a required part of offline tests. No successful live-source retrieval is claimed without a saved response.

These are query clients, not complete downloadable database mirrors or incremental change-feed integrations. Refresh is supported internally by the base client, but source-specific historical deltas, cursor resume state and release reconciliation remain unimplemented. All automatic entity linking and evidence polarity extraction require additional curation.

## Implemented real-data ETL

`backend/app/ingestion.py` adds a bounded, source-specific transformation from the live Open Targets GraphQL API into the validated graph schema. The 8 November 2026 API uses MONDO disease identifiers, `drugAndClinicalCandidates` and the `APPROVAL` stage string. The adapter was verified against the live schema rather than assuming the older `knownDrugs`/numeric-phase contract.

Disease-gene edges retain only the `genetic_association` datatype score from direct associations, not the aggregate score or known-drug support. Drug-target edges preserve reported mechanism/action text without assuming the pharmacological direction is beneficial for a disease. Explicit Ensembl IDs, ChEMBL IDs, UniProt Swiss-Prot cross-references and Reactome pathway IDs are retained. The source `APPROVAL` stage creates TREATS labels; other reported stages create INVESTIGATED_IN labels. Both are source assertions, not independent regulatory determinations. Publications are unreviewed disease-context metadata nodes without efficacy-support edges.

Each snapshot under `data/real/<sha256>/` contains raw response envelopes, the normalized dataset and a manifest. SHA-256 covers canonicalized response envelopes including retrieval timestamps and excluding the transient cache-hit flag. Retrieved timestamps and content hashes identify the observed source snapshot; there is no claim that these are an official historical database release. A second acquisition during the cache lifetime reproduces the same snapshot. See [real case study methodology](real_case_studies.md) for source selection and biases.

Open Targets aggregates ChEMBL, Reactome, UniProt and genetic evidence; their presence does not constitute independent source replication. Preserve upstream attribution and inspect [Open Targets data access](https://platform-docs.opentargets.org/data-access) and [terms](https://platform.opentargets.org/terms-of-use) before redistribution. Europe PMC article metadata, abstracts and full text have different reuse conditions; this project retains metadata and does not claim publisher-content redistribution rights.

On real curated graphs the evidence agents retrieve unreviewed Europe PMC publication metadata and openFDA label sections for up to three highest-model-score candidates. Each lookup has a 20-second overall deadline. Publication IDs/DOIs are deduplicated. Search hits do not establish relevance, study design or positive/negative findings; label ingredient/formulation identity and clinical applicability require review. Neither contributes a positive ranking component automatically. Synthetic graph entities never trigger external queries. See [openFDA label API](https://open.fda.gov/apis/drug/label/how-to-use-the-endpoint/); these records must not be relied on for medical-care decisions.

DrugBank, DisGeNET, OMIM and KEGG are intentionally not implemented because access/license conditions vary. NCBI Gene, MONDO, Disease Ontology, RxNorm, Ensembl and Gene Ontology bulk ingestion are also not implemented. No restricted service is scraped or bypassed.

Technical references: [Europe PMC REST](https://europepmc.org/RestfulWebService), [ChEMBL API](https://chembl.gitbook.io/chembl-interface-documentation/web-services/chembl-data-web-services), [Open Targets API](https://github.com/opentargets/platform-docs/blob/main/data-access/graphql-api.md), [Reactome official client](https://github.com/reactome/reactome2py/blob/master/reactome2py/content.py). License strings in response envelopes are attribution reminders; verify current source and upstream terms before redistribution.
