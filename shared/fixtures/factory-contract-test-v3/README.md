# Schema3 contract-only fixture

Synthetic manually authored state, not executed production history. A 500 kg unallocated stock coil and two 1000 kg inputs → two 950 kg outputs + 100 kg loss demonstrate nullable provenance and N:M batch storage. Run time is fixed; there are no fabricated production events. The two outputs have no claimed production-lot history.

`bundle.json` pins the exact actual bytes of collections and test-only schema/reader descriptors. `domain.json` hydrates the collections with run identity and that manifest SHA256. Profile `v3_contract_test` is only for constructor dependency injection. These files cannot satisfy canonical bundle admission. No GLB, motion, source asset, production policy or coverage proof is claimed.

`contract-test-world.json` is an exact byte copy of the existing validated T3 `factory-world-v2-example.json`, a small synthetic contract graph. Custody slots/sockets resolve to its road, rail and roller slots. This supplies actual graph identity for contract tests; it is not the future full factory site. No production equipment behavior is inferred from this graph.
