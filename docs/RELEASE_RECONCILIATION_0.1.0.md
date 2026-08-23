# Release 0.1.0 Reconciliation Ledger

This ledger is committed with the release-prep change and was reconciled from
the fresh `origin/main` snapshot `d9f414cc51ae60c0d78a3bbbb176ecac179afeac`
on 2026-08-22. It preserves the Wave-1 first-parent, merged-PR, and
non-first-parent ledgers as an owner-local audit artifact. The human-first
release narrative remains in `CHANGELOG.md`; rows below are evidence and
classification, not a commit-dump substitute for that narrative.

## 10. First-Parent Reconciliation

Every first-parent commit in the root-to-current range is listed. Merge commits are classified using their merged PR row; generated KAG-only commits are retained as `generated churn`, not silently dropped. `changelog-worthy` means one release-note item or a deliberate combined item; `internal/noise` and `duplicate` are retained for audit only.

| # | Date | Commit | Classification | Subject |
|---:|---|---|---|---|
| 1 | 2026-08-10 | `d9f414cc51ae60c0d78a3bbbb176ecac179afeac` | changelog-worthy | Pin accepted aoa-kag owner-family DAG (#186) |
| 2 | 2026-07-29 | `5a5219ef027df029313fc527c71a8764cfbd193e` | changelog-worthy | Require an explicit Course owner root for MCP (#185) |
| 3 | 2026-07-26 | `3f322cbd5c874744f29039b560044641862a7822` | changelog-worthy | Make Course eval and release scenarios owner-driven (#184) |
| 4 | 2026-07-17 | `346254a134f6f7dd14c6edc0a519a2681d8813a9` | changelog-worthy | Adopt portable KAG index family (#183) |
| 5 | 2026-07-14 | `10c7e75707cea43ee493496f005b4b6ceeab7281` | changelog-worthy | Add course connector local stats port |
| 6 | 2026-07-13 | `948315ca430d575e40ed49be788e7bfbab6a7602` | changelog-worthy | Publish canonical repository KAG indexes (#181) |
| 7 | 2026-07-10 | `2553848e089fc143957a6133f7babe04ed573415` | changelog-worthy | Add repository KAG index family (#180) |
| 8 | 2026-07-10 | `64a36becd3851c23bb2829dc0eb936dc9b9d3f47` | changelog-worthy | Pin deterministic repo-local KAG index gate (#178) |
| 9 | 2026-07-09 | `a1038187f16669cccdc7663d3fb239c9c432d8fe` | changelog-worthy | Sanitize the public connector seed (#179) |
| 10 | 2026-07-09 | `a4e2d93f4189e3d2d83cc8dd4ef15acca5a12526` | changelog-worthy | Merge pull request #177 from 8Dionysus/codex/bm25-retrieval |
| 11 | 2026-07-09 | `f9f4be7c6934f9670439ab03db1baf8393b9ee0b` | changelog-worthy | Enforce repo-local KAG index parity (#176) |
| 12 | 2026-07-09 | `2919ce3795dca2c896071ec7d06eac9442b0643b` | changelog-worthy | Merge pull request #175 from 8Dionysus/codex/corpus-integrity |
| 13 | 2026-07-09 | `21c489709f431d6103262abd2e83d184bc4461ea` | changelog-worthy | Merge pull request #174 from 8Dionysus/codex/ingest-completeness |
| 14 | 2026-07-09 | `96f370af0c5b880d1e9932716d9bd94e6906ac97` | changelog-worthy | Merge pull request #173 from 8Dionysus/codex/connected-portfolio-quality |
| 15 | 2026-07-08 | `10e1ae1f2d4b3f1ca7526938e1ee160b4bf8091e` | changelog-worthy | Harden course connector review contracts |
| 16 | 2026-07-08 | `7551c58f461dcd76c2ba98ecd2e012967148c427` | changelog-worthy | Merge pull request #171 from 8Dionysus/codex/fix-browser-audit-kag-validation |
| 17 | 2026-07-08 | `feba995f1caea9dcd83291a2027212608257c05b` | changelog-worthy | Fix course source answer review follow-ups |
| 18 | 2026-07-08 | `67944a0f85d02e5332ce17a63bb3a13948e23ae2` | changelog-worthy | Harden source answer readiness contracts |
| 19 | 2026-07-08 | `0c1d4dfb1fdcd8b01a172c4b6f19361ec0bbd4cf` | changelog-worthy | Block external semantic providers by path alias |
| 20 | 2026-07-08 | `ac5fa648602e0411c16aa1c3ae34a8f9a6dbde5e` | generated churn | Refresh course connector KAG source index (#167) |
| 21 | 2026-07-08 | `fca4c0f50e7e455b15351bb46de0b030d2511a94` | changelog-worthy | Improve portfolio ranking and source catalog status |
| 22 | 2026-07-08 | `380308bfb27834d76f37e257ee156037388951c7` | changelog-worthy | Fix course connector follow-up review issues (#165) |
| 23 | 2026-07-08 | `ef75fd3c1732c2ee2a1bfc657f38e91e37d9b874` | generated churn | Refresh course connector KAG source index (#164) |
| 24 | 2026-07-08 | `4752c840f7640ef8730b8ddcfdd7fd139a3ac8d4` | changelog-worthy | Expose sync coverage counts in source catalog (#163) |
| 25 | 2026-07-08 | `fb080273838bcbb03dedf65f7ce169f6fff56010` | changelog-worthy | Clean portfolio source answer summaries (#162) |
| 26 | 2026-07-08 | `e4d140a4d1e5a0247aede16a9d0e815f59ea9c09` | changelog-worthy | Fix symbolic course token retrieval (#161) |
| 27 | 2026-07-08 | `e0633f59c3268d714caee211ba393e736438fdde` | changelog-worthy | Fix older course review regressions (#160) |
| 28 | 2026-07-08 | `f2781fec264f56e9bbb3d7870ec2f4077911a9b8` | changelog-worthy | Fix connector review regressions (#159) |
| 29 | 2026-07-08 | `536f7202ae7d80dc1e5065cd08dc38841800f81e` | changelog-worthy | Harden fresh local grounded retrieval quality (#158) |
| 30 | 2026-07-08 | `cca5c2912a99af3c7460281304df3ae8c67f7ce5` | generated churn | Refresh course connector KAG source index (#157) |
| 31 | 2026-07-08 | `8addfa3df76015f051e74175c06bc36aead1d727` | changelog-worthy | Tighten source answer readiness contract (#156) |
| 32 | 2026-07-08 | `1d6deaa8024b7069b77c84b6d4468794f81fa18f` | changelog-worthy | Capture Skillspace API catalog discovery (#155) |
| 33 | 2026-07-08 | `7c0632bcc025a62b6b4a00a918d0e81736f1d2c4` | changelog-worthy | Add intent-gated temporal retrieval eval (#154) |
| 34 | 2026-07-08 | `d4899df6592678e77c647f5bf294b46b1ba3517a` | changelog-worthy | Add grounded portfolio quality for source answers (#153) |
| 35 | 2026-07-08 | `6f73877c4a5e4b9ccee527f5713023cac2671961` | changelog-worthy | Add place-aware retrieval quality eval (#152) |
| 36 | 2026-07-08 | `7e076807d570f2765c7f4dbca686305262f68d64` | changelog-worthy | Normalize Firefox cookie expiry for Playwright (#151) |
| 37 | 2026-07-08 | `ee5c8e27ab2262b6a84c05608a6673762159fe0a` | generated churn | Refresh course connector KAG index |
| 38 | 2026-07-08 | `bdad76126388d755ea8975ded60ce3dacfeedb4a` | changelog-worthy | Add fresh-local-grounded retrieval quality (#150) |
| 39 | 2026-07-08 | `b2475cb4b95f2cdfa0f49942dec6be8b0210807c` | generated churn | Refresh course connector KAG index |
| 40 | 2026-07-08 | `329fb2c480475d5140c8b16f423cae9164fec48e` | changelog-worthy | Merge pull request #149 from 8Dionysus/codex/remove-course-runbook-overcode |
| 41 | 2026-07-08 | `9ee50cdba8998fadcc37253923780cb072770ea6` | generated churn | Refresh course connector KAG index |
| 42 | 2026-07-08 | `6c726b4ee8567b9bcd8a19e3622d847b2fd5aaf5` | changelog-worthy | Merge pull request #148 from 8Dionysus/codex/preserve-stepik-repair-budget |
| 43 | 2026-07-08 | `2cc6814eec3c9bef9c602b55828d751834df6cf0` | changelog-worthy | Merge pull request #147 from 8Dionysus/codex/stepik-budget-mcp-plans |
| 44 | 2026-07-08 | `679a8fbdae9cef02c9ec7c22041fd2d1c71ab1af` | generated churn | Refresh course connector KAG source index |
| 45 | 2026-07-08 | `8a1cc5bd2bad57e1504e8626e2f2ced304403cd9` | changelog-worthy | Reuse Stepik sync for live smoke |
| 46 | 2026-07-08 | `b82bddf600e14cf6bde63496e3b1ee0d35d5a6f8` | generated churn | Refresh course connector KAG source index |
| 47 | 2026-07-08 | `75e70793103903b726b06b2eaf2b05fc237d3218` | changelog-worthy | Expose profile Firefox import route |
| 48 | 2026-07-08 | `eb750d07eb3007889d7ac423e5b0a9f0ddb7a2f2` | changelog-worthy | Expose browser Firefox import plan |
| 49 | 2026-07-08 | `2e9c76368fd4caa4e686231691454be2af6f6c5b` | changelog-worthy | Document multisource live proof (#143) |
| 50 | 2026-07-08 | `3415829a4a273cccb8efe691779d12167c909ef5` | changelog-worthy | Add materialize content counts (#142) |
| 51 | 2026-07-08 | `09033b7b01fbb2524aa75b3544894d6970555dba` | changelog-worthy | Merge pull request #141 from 8Dionysus/feat/source-matrix-portfolio-coverage |
| 52 | 2026-07-08 | `efa787efab8d11d0dd787d2ef6ba3d4b7a858868` | changelog-worthy | Merge pull request #140 from 8Dionysus/feat/getcourse-chatium-discovery |
| 53 | 2026-07-08 | `6829ffb2bc9e332c172bb530d41087074b2edd5c` | generated churn | Merge pull request #139 from 8Dionysus/codex/refresh-kag-after-stepik-grades |
| 54 | 2026-07-08 | `bf2d34c737cbedad4aebffde02e3e37a5920a21c` | changelog-worthy | Merge pull request #138 from 8Dionysus/codex/stepik-course-grades-discovery |
| 55 | 2026-07-08 | `f642d9567fdd4e6075a8718f88e42c44074ea9cc` | generated churn | Merge pull request #137 from 8Dionysus/codex/refresh-kag-after-firefox-import |
| 56 | 2026-07-08 | `454da73d3fa32b050e1630c916f53bf8b381fd68` | changelog-worthy | Merge pull request #136 from 8Dionysus/codex/firefox-stepik-state-import |
| 57 | 2026-07-07 | `ac1233a8de759556093c3f76d43c6ee96bd83660` | changelog-worthy | Merge pull request #135 from 8Dionysus/codex/refresh-kag-after-stepik-browser-auth |
| 58 | 2026-07-07 | `3668866e9f8aef0e06639a463bd80529d38fb638` | changelog-worthy | Merge pull request #134 from 8Dionysus/codex/stepik-browser-state-auth |
| 59 | 2026-07-07 | `db322cd1d36d0eefa7c4796e84f918d256020ae0` | changelog-worthy | Merge pull request #133 from 8Dionysus/codex/source-registry-query-eval |
| 60 | 2026-07-07 | `9fd651573993155526bf7f93e1958bfc9897bd3b` | changelog-worthy | Merge pull request #131 from 8Dionysus/codex/source-registry-readiness |
| 61 | 2026-07-07 | `893726582bc7a366a9470537df8b67bfd83332ed` | changelog-worthy | Merge pull request #130 from 8Dionysus/codex/sources-answer-matrix |
| 62 | 2026-07-07 | `f098e8d81a3142159ec182beceadf62e2b13d295` | changelog-worthy | Merge pull request #129 from 8Dionysus/codex/cli-sources-list-catalog |
| 63 | 2026-07-07 | `d8fef25f184d666a7481e1e2395ed7f6aa844512` | changelog-worthy | Merge pull request #128 from 8Dionysus/codex/install-route-sources-answer-proof |
| 64 | 2026-07-07 | `ad3aaa0f7794cac8ee793f01ed3895096698a388` | changelog-worthy | Merge pull request #127 from 8Dionysus/codex/source-answer-command-hints |
| 65 | 2026-07-07 | `7dd12f5a57bf91a398c6b321d43a3df9dbcd55cd` | changelog-worthy | Merge pull request #126 from 8Dionysus/codex/cli-sources-answer |
| 66 | 2026-07-07 | `c8f04ffd03def502a9456a1f4a9a9c2c849ea7d3` | changelog-worthy | Merge pull request #125 from 8Dionysus/codex/mcp-sources-answer |
| 67 | 2026-07-07 | `bba0a9ce0d85f15b0eaa69088bc56981b5205619` | changelog-worthy | Merge pull request #124 from 8Dionysus/codex/source-answer-catalog-backfill |
| 68 | 2026-07-07 | `f94a2c987313303643ed7b28f4c873b87a764b53` | changelog-worthy | Merge pull request #123 from 8Dionysus/codex/mcp-source-answer |
| 69 | 2026-07-07 | `bee8214dba145902b9be0aaa8e9e8c78717be755` | changelog-worthy | Merge pull request #122 from 8Dionysus/codex/source-catalog-connected-runs |
| 70 | 2026-07-07 | `f8f71c8d68efa073c5f50e9eff3fab44ff212fba` | changelog-worthy | Merge pull request #121 from 8Dionysus/codex/mcp-source-catalog |
| 71 | 2026-07-07 | `1df6bf33b509a0a75ad759b6fdace6218dec7f1d` | changelog-worthy | Merge pull request #120 from 8Dionysus/codex/ready-subset-connected-plan |
| 72 | 2026-07-07 | `86d4764a135a53964adef12fb8b5775da72f6a69` | changelog-worthy | Merge pull request #119 from 8Dionysus/codex/browser-access-denied-lessons |
| 73 | 2026-07-07 | `28e190a89206069021f7604e0a25be96126c20db` | changelog-worthy | Merge pull request #118 from 8Dionysus/codex/connected-query-matrix |
| 74 | 2026-07-07 | `7c25cc1a3cb3856022e4dcd2f4b161fab80bb2bd` | changelog-worthy | Merge pull request #117 from 8Dionysus/codex/preserve-browser-live-source-id |
| 75 | 2026-07-07 | `162cdcd4790b8fe53210b3a1e9e8f6655c872401` | generated churn | Refresh KAG source surface index |
| 76 | 2026-07-07 | `44995e05dc677c1f91db954a84fccc3c0297999b` | changelog-worthy | Add repo-local KAG source surface index |
| 77 | 2026-07-07 | `eabbe1f6fda1e56db8e00af99c98ab1e200d1f23` | changelog-worthy | Merge pull request #116 from 8Dionysus/codex/getcourse-full-lesson-crawl |
| 78 | 2026-07-07 | `4f2a79a3bc8b2480dcaa4f07e511ccd98d836237` | changelog-worthy | Merge pull request #115 from 8Dionysus/preauth-readiness-gate-clean |
| 79 | 2026-07-07 | `5e6facd52dea82ac544bd3b99d310627d43a9f09` | changelog-worthy | Merge pull request #114 from 8Dionysus/codex/local-kag-provider-home |
| 80 | 2026-07-06 | `ff395c5db978e10ba277053da54952ec6a86fa04` | changelog-worthy | Merge pull request #113 from 8Dionysus/codex/connected-run-query-packet |
| 81 | 2026-07-06 | `c5ca58fda7ed0716f6f12ad98aa2dd221ab976f4` | changelog-worthy | Merge pull request #112 from 8Dionysus/codex/mcp-connected-run-plan |
| 82 | 2026-07-06 | `a3e5d9ebb4d9614088bbc23854fdf6d6e2e6d8cd` | changelog-worthy | Merge pull request #111 from 8Dionysus/codex/mcp-connected-run |
| 83 | 2026-07-06 | `4f83f7208a68dcb476a54f7f3fe628882e3ae07d` | changelog-worthy | Merge pull request #110 from 8Dionysus/codex/verify-install-mcp-answer |
| 84 | 2026-07-06 | `263331e296bf3db613888e1c3ccc5465eb9bac55` | changelog-worthy | Merge pull request #109 from 8Dionysus/codex/install-route-eval |
| 85 | 2026-07-06 | `a182f1e9b6ce9678b33565062a6ff0f913155f91` | changelog-worthy | Merge pull request #108 from 8Dionysus/codex/mcp-answer-packet |
| 86 | 2026-07-06 | `f8f5318fa0b5a9a73609cf346d42db259569ff67` | changelog-worthy | Merge pull request #107 from 8Dionysus/codex/answer-quality-packets |
| 87 | 2026-07-06 | `a5ba293c24fbdf7ad51a63a60697408e78f19f83` | changelog-worthy | Merge pull request #106 from 8Dionysus/codex/mcp-profile-run-plan |
| 88 | 2026-07-06 | `60e52071dccb5eaf97eb284758078311c0a7d4ba` | changelog-worthy | Merge pull request #105 from 8Dionysus/connect-profile-run |
| 89 | 2026-07-06 | `6b37939e7f3a5853d90b0057f94a4d0e4e9267f4` | changelog-worthy | Merge pull request #104 from 8Dionysus/retrieval-loop-eval |
| 90 | 2026-07-06 | `5768c514e6e31ddebf1230144ddf0890ef85a79e` | changelog-worthy | Merge pull request #103 from 8Dionysus/stable-sync-identity |
| 91 | 2026-07-06 | `e95a4f6b970dea9502089162f6e119addf39c4fa` | changelog-worthy | Merge pull request #102 from 8Dionysus/codex/query-plan-mode-aware-query |
| 92 | 2026-07-06 | `c54ee37c8dfa6cdb42834a6ddcf7687f957900a5` | changelog-worthy | Merge pull request #101 from 8Dionysus/codex/sync-semantic-artifacts |
| 93 | 2026-07-06 | `6e1cbd7716fc12dea32d49768a2c8eba9863aba7` | changelog-worthy | Merge pull request #100 from 8Dionysus/codex/refresh-hint-query-commands |
| 94 | 2026-07-06 | `206befc3ec46d4ef0fa4743270f45fd71d202c9c` | changelog-worthy | Merge pull request #99 from 8Dionysus/codex/query-plan-lesson-context |
| 95 | 2026-07-06 | `2bcaaf067a6bf77ec8125767851c023327f9d235` | changelog-worthy | Merge pull request #98 from 8Dionysus/codex/cli-lesson-context |
| 96 | 2026-07-06 | `267905c5700eccfa008a297c186c5d87a61052ee` | changelog-worthy | Merge pull request #97 from 8Dionysus/codex/lesson-context-graph |
| 97 | 2026-07-06 | `ab5a188c9c2b0ac2aaf3c5233d6c79c9d4a9b4a0` | changelog-worthy | Merge pull request #96 from 8Dionysus/codex/evidence-chain-snippets |
| 98 | 2026-07-06 | `a3239fa2d5f04c87960bd01d301e7ab8fff3d051` | changelog-worthy | Merge pull request #95 from 8Dionysus/codex/browser-crawl-placeholder-evidence |
| 99 | 2026-06-30 | `c7200e6873f16245bd73455992d0e9557693dc5f` | changelog-worthy | Merge pull request #94 from 8Dionysus/codex/connected-snapshot-audit-status |
| 100 | 2026-06-30 | `e4deb70630b65582b0791a28475614521c3bdf36` | changelog-worthy | Audit page-scoped caption resources |
| 101 | 2026-06-30 | `41bb8e7e2fb239ff86fa1b08c4d7e4d679a80147` | changelog-worthy | Merge pull request #92 from 8Dionysus/codex/embed-snapshot-audits-in-smoke |
| 102 | 2026-06-30 | `f432f1b268d068bc4b2883b854021e95fabac4ea` | changelog-worthy | Merge pull request #91 from 8Dionysus/codex/browser-snapshot-audit-mcp |
| 103 | 2026-06-30 | `a42b63b847b2bb348ee2a51f4112ef70c5aad609` | changelog-worthy | Merge pull request #90 from 8Dionysus/codex/browser-snapshot-audit |
| 104 | 2026-06-30 | `3dab4e56108e8ca42edd0c65cc4f68aaa32e2f8b` | changelog-worthy | Omit null optional answer evidence fields |
| 105 | 2026-06-30 | `183010ff06c572dc5055f6abf83a9cdcb517c589` | changelog-worthy | Validate sync run ids before checkpoint writes |
| 106 | 2026-06-30 | `e4807809ccd107fbaf65eeca5cfbfe525fcac2a6` | changelog-worthy | Require refresh hints for answer quality (#86) |
| 107 | 2026-06-30 | `f758e75da04e7fad802612eee522f18988d14f52` | changelog-worthy | Enrich answer evidence proof fields (#87) |
| 108 | 2026-06-30 | `5d32a356db7ce51af41dd9abe1d26a8017539d86` | changelog-worthy | Guard runtime storage ids (#85) |
| 109 | 2026-06-30 | `00b77eebc8edaf66683e3c64e3e67254a34415c2` | changelog-worthy | Prefer selected semantic provider commands (#84) |
| 110 | 2026-06-30 | `fe48016a4c17607b511bc1d0d3d8195244557aaf` | changelog-worthy | Add smoke answer proof quality checks (#83) |
| 111 | 2026-06-30 | `d57789f15da13f7ff468ec02303c3c15018c297a` | changelog-worthy | Clean connector API surface (#82) |
| 112 | 2026-06-30 | `8b5d0c564b38d2a4abcca3fc36479378235e5f22` | changelog-worthy | Preserve connected source scope in readiness (#81) |
| 113 | 2026-06-30 | `4806afe58ec3546e319b326bb434143d9b9c293d` | changelog-worthy | Add connection profile status |
| 114 | 2026-06-30 | `b0e6168aa7a8bb05f214f349b394765c34b9aa84` | changelog-worthy | Add connection profile runbook |
| 115 | 2026-06-30 | `4ba2078710597f6904a46f6d942375944626841d` | changelog-worthy | Add connection profile handoff |
| 116 | 2026-06-30 | `c0b41bf187c4ea684dd495fd9aa45af1413673d7` | changelog-worthy | Add goal connection handoff |
| 117 | 2026-06-30 | `f92105781395ec6111765bbcbc41829098ef8c0b` | changelog-worthy | Add browser auth host candidates |
| 118 | 2026-06-30 | `825d7bb9d25fb5e1e54487a21a020b165d0756d7` | changelog-worthy | Add semantic provider preflight |
| 119 | 2026-06-30 | `0d5d578c65adf82c3d3beab88a1b53ec7953fd94` | changelog-worthy | Verify browser auth capture origins (#74) |
| 120 | 2026-06-30 | `f18bc70df3187b262a16aec28edb78d5045e65f5` | changelog-worthy | Scope connected plans to selected sources (#73) |
| 121 | 2026-06-30 | `b8d5517d0f1924c6b08bf94315c373554bca1ebc` | changelog-worthy | Guard live plans from fixture sources (#72) |
| 122 | 2026-06-30 | `8a35445a627f12feefa6e1cd01b0cf17d29439ac` | changelog-worthy | Expose goal audit through MCP (#71) |
| 123 | 2026-06-30 | `c1107c33a98e60f866a213c390b4bcb1309f918f` | changelog-worthy | Add goal audit handoff (#70) |
| 124 | 2026-06-30 | `de9e86a8df2bf039762741f160b9097dbab10a5d` | changelog-worthy | Expose future platform topology (#69) |
| 125 | 2026-06-30 | `cf84ea1203d73e359ab2feb7a13f8bfe979f1bba` | changelog-worthy | Route readiness through connected repair lanes (#68) |
| 126 | 2026-06-30 | `f5a69a56e8fa4680254b9cfbd1c34f296fad02e6` | changelog-worthy | Classify connected run repair lanes (#67) |
| 127 | 2026-06-30 | `a97f91d3c2aa113fc2f72fbcc0b0062fd6b1ab4d` | changelog-worthy | Expose MCP commands in connected query handoff (#66) |
| 128 | 2026-06-30 | `54540be4f25f1135e72ff542af3bf8e1629ba7eb` | changelog-worthy | Preserve connected run bounds in readiness (#65) |
| 129 | 2026-06-30 | `17dfb6457928172f65f1f10714ada08e8405c441` | changelog-worthy | Record connected run execution options (#64) |
| 130 | 2026-06-30 | `46359a926e7f1621145c56f45bc3abf55c78e78e` | changelog-worthy | Fix connected handoff review followups (#63) |
| 131 | 2026-06-30 | `dc3c88be9515dba971cdc3010ca22a3243fc612e` | changelog-worthy | Carry connected run handoff through readiness (#62) |
| 132 | 2026-06-30 | `c871f315a773685cfb2592e9bc14749a56f65d9c` | changelog-worthy | Expose connected run handoff in launch plans (#61) |
| 133 | 2026-06-30 | `ca2a087b24c87531f18d07813d7432d32c4318c7` | changelog-worthy | Propagate browser link pattern through connected routes (#60) |
| 134 | 2026-06-30 | `9825df23d92a37b4ea64f7a4cb6ba195c29ab849` | changelog-worthy | Add connected run query handoff (#59) |
| 135 | 2026-06-30 | `99205c4a955f9b7067e2cc383156ce61ffbe9192` | changelog-worthy | Assert install-route stdio tool responses (#58) |
| 136 | 2026-06-30 | `db5a8529e5ff6b47ea10c70d604246a544a88510` | changelog-worthy | Expose connected live readiness flag (#57) |
| 137 | 2026-06-30 | `6324f1c82adf3249c6a30e5aab950f2b8d98e032` | changelog-worthy | Harden bootstrap route validation (#56) |
| 138 | 2026-06-30 | `1422b7a604b2c6c4c7971549deeba8548d185deb` | changelog-worthy | Default connected plans to priority platforms (#55) |
| 139 | 2026-06-30 | `8e2df988e0a63a5f0df25ed591b61ed469358398` | changelog-worthy | Harden connector readiness followups |
| 140 | 2026-06-30 | `31f83df079a877f80eadaa156f202df279c4ee2c` | changelog-worthy | Prove all priority adapters in bootstrap (#53) |
| 141 | 2026-06-30 | `c101aa8564075f7fc92b705166c04bd9972fab5d` | changelog-worthy | Add fixture bootstrap route (#52) |
| 142 | 2026-06-30 | `1dba37d2f976d1ebdbbf811fb4d207cdca1db158` | changelog-worthy | Add connector readiness audit (#51) |
| 143 | 2026-06-30 | `65ad999aa9d8a2b51ed2364837ad74ce0f54eca1` | changelog-worthy | Fix connected-run state file docs (#50) |
| 144 | 2026-06-30 | `bc4df1720de482490a62b3a20a8c1e8f3a9e7f18` | changelog-worthy | Fix connected run status MCP default (#48) |
| 145 | 2026-06-30 | `fbd97b321d45ea4832673bd6d1b86eb32327398e` | changelog-worthy | Expand MCP ingest status (#49) |
| 146 | 2026-06-30 | `33f0104275c4d7611c7de423eabb57f1a7d0ac8a` | changelog-worthy | Harden live browser connected run (#47) |
| 147 | 2026-06-30 | `227876824bb76bff8e056332c86e1f3a5178738b` | changelog-worthy | Add connected run status (#46) |
| 148 | 2026-06-30 | `c66a49288e6c68aac5f69a6fd290d897e4c55721` | changelog-worthy | Guard selected live source runs (#45) |
| 149 | 2026-06-30 | `a1b6e13a6b6039e6cf98d60b07673723162a458c` | changelog-worthy | Document Stepik live connected run (#44) |
| 150 | 2026-06-30 | `cf4af5c4b823e84dc00646bc12f1c093466bd7ac` | changelog-worthy | Add connected calibration run (#43) |
| 151 | 2026-06-30 | `c75d367c0bc3c52c7a2336b1b1d19504423b4e04` | changelog-worthy | Fix selected course refresh handoffs (#42) |
| 152 | 2026-06-30 | `9fef0b8a3e29f7f89f7481cdc77048827ee98478` | changelog-worthy | Add source scoped sync commands (#41) |
| 153 | 2026-06-30 | `75eb4be89b4f940ff4e5b1c0d97f0fffdf8131a8` | changelog-worthy | Add query refresh cycle (#40) |
| 154 | 2026-06-30 | `777447e3c6ddb45ae8e03c34392ccb1e43c9dd4c` | changelog-worthy | Add source refresh handoff hints (#39) |
| 155 | 2026-06-30 | `c30fa224b3ea4a23847f8755488f7cc409ee9304` | changelog-worthy | Use portable generated artifact paths (#38) |
| 156 | 2026-06-30 | `79f0711585c3cea06e31c71476ef2531443ccb29` | changelog-worthy | Document portable calibration artifacts (#37) |
| 157 | 2026-06-30 | `6a405c72ba86484169ddee5773e0124d434854cf` | changelog-worthy | Add HTTP JSON semantic provider (#36) |
| 158 | 2026-06-30 | `6ebb4bc5e7d1b5295fd1ab8a84156ae79e82bd59` | changelog-worthy | Document runbook artifact fallback (#35) |
| 159 | 2026-06-30 | `c6d47ca02ed014b9635b91a1a835f2f3de2ff201` | changelog-worthy | Add live calibration intake (#34) |
| 160 | 2026-06-30 | `5bef19de80a831a8134535f882fc0f5692240ab5` | changelog-worthy | Add connected source runbook (#33) |
| 161 | 2026-06-30 | `78e8d70bdc07a9f2b09c15ddd9aa9acf1befd769` | changelog-worthy | Add browser auth handoff plans (#32) |
| 162 | 2026-06-30 | `72cb942b65a813299ea45e45b9dde2d81e6748e7` | changelog-worthy | Harden connected live launch scope (#31) |
| 163 | 2026-06-30 | `0409db97cee2c7e39030e76dc779d047a5d0601c` | changelog-worthy | Add connected source launch plan (#30) |
| 164 | 2026-06-30 | `f1e3942f1705b3c9b431564ed37426673de6f716` | changelog-worthy | Add live calibration transcript health (#29) |
| 165 | 2026-06-30 | `a588dc39b197eb10fd757c394f675e98890520a9` | changelog-worthy | Add browser caption sidecars (#28) |
| 166 | 2026-06-30 | `25306d5ce0904627d43154989b61cc313e4b025e` | changelog-worthy | Add browser transcripts and calibration guards (#27) |
| 167 | 2026-06-30 | `7e49f81a4556ccca5ea521eaf87dbc39a9396193` | changelog-worthy | Add MCP evidence report |
| 168 | 2026-06-30 | `e0315c4982f87e2a0005646acf7adda241ff5bdc` | changelog-worthy | Add live calibration packets |
| 169 | 2026-06-30 | `b4a94a3333c942b6b6d23eca4fe51384354b4068` | changelog-worthy | Preserve adapter authority metadata (#24) |
| 170 | 2026-06-30 | `ae17d38368b264ffc8240d8ecceb3cfae56b6acb` | changelog-worthy | Add authority ranking eval (#23) |
| 171 | 2026-06-30 | `47757030c3ee65b8dd23eb2c1b95945ebfd650e7` | changelog-worthy | Harden live readiness checks (#22) |
| 172 | 2026-06-29 | `43f9074c7de07e197e901d6f8054971e2c71160b` | changelog-worthy | Add freshness ranking eval (#21) |
| 173 | 2026-06-29 | `c683fc5e23281a9be32f71297c949d4f80f31356` | changelog-worthy | Add answer quality eval |
| 174 | 2026-06-29 | `82698d6d682b93ede96f6465eab94446ec0bec8e` | changelog-worthy | Expose live preflight over MCP |
| 175 | 2026-06-29 | `9df8699a643ea45f9ff31db5c1bbe1cd9c694357` | changelog-worthy | Add live preflight readiness |
| 176 | 2026-06-29 | `023f1bc4200d7668af225668a59817b31bd26f26` | changelog-worthy | Add Stepik account discovery |
| 177 | 2026-06-29 | `a3ddf80e0e55dceb94197c58a982b0bfe93994c4` | changelog-worthy | Harden MCP runtime and retrieval guards |
| 178 | 2026-06-29 | `27595c731f2845400b3d2048860a9c618a1bc665` | changelog-worthy | Add browser auth state onboarding |
| 179 | 2026-06-29 | `dd6dcc4bb0b2b1f2744251ae7b16040cc7e07cb0` | changelog-worthy | Harden smoke route guards |
| 180 | 2026-06-29 | `a2a3325237c933b545e0a26669c3e91ea4cb87db` | changelog-worthy | Add semantic index baseline |
| 181 | 2026-06-29 | `dd6d0bea8bef66a88efa8c8d019dde845d35ec18` | changelog-worthy | Add Stepik smoke reports |
| 182 | 2026-06-29 | `b6afad0c2242deb2aa3b08805ee97a6fe009d490` | changelog-worthy | Add Stepik source sync |
| 183 | 2026-06-29 | `493ca51e7468c56e1beb73cf015fa5ec28ac3930` | changelog-worthy | Add Stepik full-course batching |
| 184 | 2026-06-29 | `87aed1954d8b2fb72d763061620f60e015553644` | changelog-worthy | Add browser smoke reports (#9) |
| 185 | 2026-06-29 | `f88d5b168926edb359f9fb42a7fae826648260fc` | changelog-worthy | Add live pagination and DOM heuristics (#8) |
| 186 | 2026-06-29 | `802d106f179ea688f644ef5443e50dcb4e208e7f` | changelog-worthy | Add browser progress comments and pagination proof (#7) |
| 187 | 2026-06-29 | `00c0416e9a3fb7a13e8a500f08da04f997588a93` | changelog-worthy | Add browser source sync checkpoints (#6) |
| 188 | 2026-06-29 | `0a7fce40869e065cb1bb751a68b3c04fa3b42ae1` | changelog-worthy | Add browser account source discovery (#5) |
| 189 | 2026-06-29 | `2d7384e953c640a22797d47afde8b32d982e969f` | changelog-worthy | Add browser course-tree crawl routes (#4) |
| 190 | 2026-06-29 | `4cd77078f1ac4db925d9151113df02adda96829e` | changelog-worthy | Add browser session hard adapters (#3) |
| 191 | 2026-06-29 | `f7cad9d072a6ccb631e9b7ce8857c73319b0ad6b` | changelog-worthy | Add Stepik clean API adapter (#2) |
| 192 | 2026-06-29 | `81a84a620564f6c6ef4c65ff5e07644022e5bcb1` | changelog-worthy | Document connector status (#1) |
| 193 | 2026-06-29 | `4787a81f23b1158dad3a12299e99a340c6623084` | generated churn | Track auth route and kag index sources |
| 194 | 2026-06-29 | `5128e985186b88f7ec3c14fa5ad0451280b429d6` | changelog-worthy | Initialize course connector |

Exact command used: `git log --first-parent --format='%H%x09%ad%x09%s' --date=iso-strict main`.


## 11. Merged-PR Reconciliation Ledger

All 186 PRs are merged. Each PR is classified below as a separate changelog item, generated churn, duplicate, internal/noise, or a contract/documentation item that remains part of the release audit. PR titles and URLs are from live GitHub at observation.

| PR | Merge SHA | Merged at | Classification | Title | URL |
|---:|---|---|---|---|---|
| 1 | `81a84a620564f6c6ef4c65ff5e07644022e5bcb1` | 2026-06-30T00:23:48Z | changelog-worthy | Document connector status | https://github.com/8Dionysus/aoa-course-connector/pull/1 |
| 2 | `f7cad9d072a6ccb631e9b7ce8857c73319b0ad6b` | 2026-06-30T01:14:10Z | changelog-worthy | Add Stepik clean API adapter | https://github.com/8Dionysus/aoa-course-connector/pull/2 |
| 3 | `4cd77078f1ac4db925d9151113df02adda96829e` | 2026-06-30T01:23:22Z | changelog-worthy | Add browser-session hard adapters | https://github.com/8Dionysus/aoa-course-connector/pull/3 |
| 4 | `2d7384e953c640a22797d47afde8b32d982e969f` | 2026-06-30T01:35:29Z | changelog-worthy | Add browser course-tree crawl routes | https://github.com/8Dionysus/aoa-course-connector/pull/4 |
| 5 | `0a7fce40869e065cb1bb751a68b3c04fa3b42ae1` | 2026-06-30T01:47:14Z | changelog-worthy | Add browser account source discovery | https://github.com/8Dionysus/aoa-course-connector/pull/5 |
| 6 | `00c0416e9a3fb7a13e8a500f08da04f997588a93` | 2026-06-30T01:59:28Z | changelog-worthy | Add browser source sync checkpoints | https://github.com/8Dionysus/aoa-course-connector/pull/6 |
| 7 | `802d106f179ea688f644ef5443e50dcb4e208e7f` | 2026-06-30T02:17:29Z | changelog-worthy | [codex] Add browser progress comments and pagination proof | https://github.com/8Dionysus/aoa-course-connector/pull/7 |
| 8 | `f88d5b168926edb359f9fb42a7fae826648260fc` | 2026-06-30T02:27:08Z | changelog-worthy | [codex] Add live pagination and DOM heuristics | https://github.com/8Dionysus/aoa-course-connector/pull/8 |
| 9 | `87aed1954d8b2fb72d763061620f60e015553644` | 2026-06-30T02:38:07Z | changelog-worthy | [codex] Add browser smoke reports | https://github.com/8Dionysus/aoa-course-connector/pull/9 |
| 10 | `493ca51e7468c56e1beb73cf015fa5ec28ac3930` | 2026-06-30T02:51:15Z | changelog-worthy | [codex] Add Stepik full-course batching | https://github.com/8Dionysus/aoa-course-connector/pull/10 |
| 11 | `b6afad0c2242deb2aa3b08805ee97a6fe009d490` | 2026-06-30T03:02:30Z | changelog-worthy | [codex] Add Stepik source sync | https://github.com/8Dionysus/aoa-course-connector/pull/11 |
| 12 | `dd6d0bea8bef66a88efa8c8d019dde845d35ec18` | 2026-06-30T03:11:55Z | changelog-worthy | [codex] Add Stepik smoke reports | https://github.com/8Dionysus/aoa-course-connector/pull/12 |
| 13 | `a2a3325237c933b545e0a26669c3e91ea4cb87db` | 2026-06-30T03:22:10Z | changelog-worthy | [codex] Add semantic index baseline | https://github.com/8Dionysus/aoa-course-connector/pull/13 |
| 14 | `dd6dcc4bb0b2b1f2744251ae7b16040cc7e07cb0` | 2026-06-30T03:28:01Z | changelog-worthy | [codex] Harden smoke route guards | https://github.com/8Dionysus/aoa-course-connector/pull/14 |
| 15 | `27595c731f2845400b3d2048860a9c618a1bc665` | 2026-06-30T03:38:37Z | changelog-worthy | [codex] Add browser auth state onboarding | https://github.com/8Dionysus/aoa-course-connector/pull/15 |
| 16 | `a3ddf80e0e55dceb94197c58a982b0bfe93994c4` | 2026-06-30T03:51:12Z | changelog-worthy | [codex] Harden MCP runtime and retrieval guards | https://github.com/8Dionysus/aoa-course-connector/pull/16 |
| 17 | `023f1bc4200d7668af225668a59817b31bd26f26` | 2026-06-30T04:08:35Z | changelog-worthy | [codex] Add Stepik account discovery | https://github.com/8Dionysus/aoa-course-connector/pull/17 |
| 18 | `9df8699a643ea45f9ff31db5c1bbe1cd9c694357` | 2026-06-30T04:20:01Z | changelog-worthy | [codex] Add live preflight readiness | https://github.com/8Dionysus/aoa-course-connector/pull/18 |
| 19 | `82698d6d682b93ede96f6465eab94446ec0bec8e` | 2026-06-30T04:29:06Z | changelog-worthy | [codex] Expose live preflight over MCP | https://github.com/8Dionysus/aoa-course-connector/pull/19 |
| 20 | `c683fc5e23281a9be32f71297c949d4f80f31356` | 2026-06-30T04:42:56Z | changelog-worthy | [codex] Add answer quality eval | https://github.com/8Dionysus/aoa-course-connector/pull/20 |
| 21 | `43f9074c7de07e197e901d6f8054971e2c71160b` | 2026-06-30T04:57:19Z | changelog-worthy | [codex] Add freshness ranking eval | https://github.com/8Dionysus/aoa-course-connector/pull/21 |
| 22 | `47757030c3ee65b8dd23eb2c1b95945ebfd650e7` | 2026-06-30T07:01:41Z | changelog-worthy | [codex] Harden live readiness checks | https://github.com/8Dionysus/aoa-course-connector/pull/22 |
| 23 | `ae17d38368b264ffc8240d8ecceb3cfae56b6acb` | 2026-06-30T07:20:05Z | changelog-worthy | [codex] Add authority ranking eval | https://github.com/8Dionysus/aoa-course-connector/pull/23 |
| 24 | `b4a94a3333c942b6b6d23eca4fe51384354b4068` | 2026-06-30T07:38:07Z | changelog-worthy | [codex] Preserve adapter authority metadata | https://github.com/8Dionysus/aoa-course-connector/pull/24 |
| 25 | `e0315c4982f87e2a0005646acf7adda241ff5bdc` | 2026-06-30T07:55:54Z | changelog-worthy | [codex] Add live calibration packets | https://github.com/8Dionysus/aoa-course-connector/pull/25 |
| 26 | `7e49f81a4556ccca5ea521eaf87dbc39a9396193` | 2026-06-30T08:05:37Z | changelog-worthy | [codex] Add MCP evidence report | https://github.com/8Dionysus/aoa-course-connector/pull/26 |
| 27 | `25306d5ce0904627d43154989b61cc313e4b025e` | 2026-06-30T08:22:23Z | changelog-worthy | [codex] Add browser transcripts and calibration guards | https://github.com/8Dionysus/aoa-course-connector/pull/27 |
| 28 | `a588dc39b197eb10fd757c394f675e98890520a9` | 2026-06-30T08:37:23Z | changelog-worthy | [codex] Add browser caption sidecars | https://github.com/8Dionysus/aoa-course-connector/pull/28 |
| 29 | `f1e3942f1705b3c9b431564ed37426673de6f716` | 2026-06-30T08:49:27Z | changelog-worthy | [codex] Add live calibration transcript health | https://github.com/8Dionysus/aoa-course-connector/pull/29 |
| 30 | `0409db97cee2c7e39030e76dc779d047a5d0601c` | 2026-06-30T09:03:20Z | changelog-worthy | [codex] Add connected source launch plan | https://github.com/8Dionysus/aoa-course-connector/pull/30 |
| 31 | `72cb942b65a813299ea45e45b9dde2d81e6748e7` | 2026-06-30T09:14:00Z | changelog-worthy | [codex] Harden connected live launch scope | https://github.com/8Dionysus/aoa-course-connector/pull/31 |
| 32 | `78e8d70bdc07a9f2b09c15ddd9aa9acf1befd769` | 2026-06-30T09:26:02Z | changelog-worthy | [codex] Add browser auth handoff plans | https://github.com/8Dionysus/aoa-course-connector/pull/32 |
| 33 | `5bef19de80a831a8134535f882fc0f5692240ab5` | 2026-06-30T09:34:15Z | changelog-worthy | [codex] Add connected source runbook | https://github.com/8Dionysus/aoa-course-connector/pull/33 |
| 34 | `c6d47ca02ed014b9635b91a1a835f2f3de2ff201` | 2026-06-30T09:44:40Z | changelog-worthy | [codex] Add live calibration intake | https://github.com/8Dionysus/aoa-course-connector/pull/34 |
| 35 | `6ebb4bc5e7d1b5295fd1ab8a84156ae79e82bd59` | 2026-06-30T09:47:15Z | changelog-worthy | [codex] Document runbook artifact fallback | https://github.com/8Dionysus/aoa-course-connector/pull/35 |
| 36 | `6a405c72ba86484169ddee5773e0124d434854cf` | 2026-06-30T10:03:04Z | changelog-worthy | [codex] Add HTTP JSON semantic provider | https://github.com/8Dionysus/aoa-course-connector/pull/36 |
| 37 | `79f0711585c3cea06e31c71476ef2531443ccb29` | 2026-06-30T16:38:07Z | changelog-worthy | [codex] Document portable calibration artifacts | https://github.com/8Dionysus/aoa-course-connector/pull/37 |
| 38 | `c30fa224b3ea4a23847f8755488f7cc409ee9304` | 2026-06-30T16:45:37Z | changelog-worthy | [codex] Use portable generated artifact paths | https://github.com/8Dionysus/aoa-course-connector/pull/38 |
| 39 | `777447e3c6ddb45ae8e03c34392ccb1e43c9dd4c` | 2026-06-30T16:59:04Z | changelog-worthy | [codex] Add source refresh handoff hints | https://github.com/8Dionysus/aoa-course-connector/pull/39 |
| 40 | `75eb4be89b4f940ff4e5b1c0d97f0fffdf8131a8` | 2026-06-30T17:14:12Z | changelog-worthy | [codex] Add query refresh cycle | https://github.com/8Dionysus/aoa-course-connector/pull/40 |
| 41 | `9fef0b8a3e29f7f89f7481cdc77048827ee98478` | 2026-06-30T17:25:45Z | changelog-worthy | [codex] Add source scoped sync commands | https://github.com/8Dionysus/aoa-course-connector/pull/41 |
| 42 | `c75d367c0bc3c52c7a2336b1b1d19504423b4e04` | 2026-06-30T17:39:33Z | changelog-worthy | [codex] Fix course refresh handoff follow-up | https://github.com/8Dionysus/aoa-course-connector/pull/42 |
| 43 | `cf4af5c4b823e84dc00646bc12f1c093466bd7ac` | 2026-06-30T17:40:37Z | changelog-worthy | [codex] Add connected calibration run | https://github.com/8Dionysus/aoa-course-connector/pull/43 |
| 44 | `a1b6e13a6b6039e6cf98d60b07673723162a458c` | 2026-06-30T18:09:13Z | changelog-worthy | [codex] Document Stepik live connected run | https://github.com/8Dionysus/aoa-course-connector/pull/44 |
| 45 | `c66a49288e6c68aac5f69a6fd290d897e4c55721` | 2026-06-30T18:12:33Z | changelog-worthy | [codex] Guard selected live source runs | https://github.com/8Dionysus/aoa-course-connector/pull/45 |
| 46 | `227876824bb76bff8e056332c86e1f3a5178738b` | 2026-06-30T18:23:37Z | changelog-worthy | [codex] Add connected run status | https://github.com/8Dionysus/aoa-course-connector/pull/46 |
| 47 | `33f0104275c4d7611c7de423eabb57f1a7d0ac8a` | 2026-06-30T18:34:20Z | changelog-worthy | [codex] Harden live browser connected run | https://github.com/8Dionysus/aoa-course-connector/pull/47 |
| 48 | `bc4df1720de482490a62b3a20a8c1e8f3a9e7f18` | 2026-06-30T19:12:19Z | changelog-worthy | Fix connected run status MCP default | https://github.com/8Dionysus/aoa-course-connector/pull/48 |
| 49 | `fbd97b321d45ea4832673bd6d1b86eb32327398e` | 2026-06-30T19:12:15Z | changelog-worthy | [codex] Expand MCP ingest status | https://github.com/8Dionysus/aoa-course-connector/pull/49 |
| 50 | `65ad999aa9d8a2b51ed2364837ad74ce0f54eca1` | 2026-06-30T19:24:38Z | changelog-worthy | Fix connected-run state file docs | https://github.com/8Dionysus/aoa-course-connector/pull/50 |
| 51 | `1dba37d2f976d1ebdbbf811fb4d207cdca1db158` | 2026-06-30T19:31:13Z | changelog-worthy | Add connector readiness audit | https://github.com/8Dionysus/aoa-course-connector/pull/51 |
| 52 | `c101aa8564075f7fc92b705166c04bd9972fab5d` | 2026-06-30T19:41:54Z | changelog-worthy | Add fixture bootstrap route | https://github.com/8Dionysus/aoa-course-connector/pull/52 |
| 53 | `31f83df079a877f80eadaa156f202df279c4ee2c` | 2026-06-30T19:48:38Z | changelog-worthy | Prove all priority adapters in bootstrap | https://github.com/8Dionysus/aoa-course-connector/pull/53 |
| 54 | `8e2df988e0a63a5f0df25ed591b61ed469358398` | 2026-06-30T19:50:07Z | changelog-worthy | Harden connector readiness followups | https://github.com/8Dionysus/aoa-course-connector/pull/54 |
| 55 | `1422b7a604b2c6c4c7971549deeba8548d185deb` | 2026-06-30T19:57:09Z | changelog-worthy | Default connected plans to priority platforms | https://github.com/8Dionysus/aoa-course-connector/pull/55 |
| 56 | `6324f1c82adf3249c6a30e5aab950f2b8d98e032` | 2026-06-30T20:00:59Z | changelog-worthy | Harden bootstrap route validation | https://github.com/8Dionysus/aoa-course-connector/pull/56 |
| 57 | `db5a8529e5ff6b47ea10c70d604246a544a88510` | 2026-06-30T20:02:36Z | changelog-worthy | Expose connected live readiness flag | https://github.com/8Dionysus/aoa-course-connector/pull/57 |
| 58 | `99205c4a955f9b7067e2cc383156ce61ffbe9192` | 2026-06-30T20:10:33Z | changelog-worthy | Assert install-route stdio tool responses | https://github.com/8Dionysus/aoa-course-connector/pull/58 |
| 59 | `9825df23d92a37b4ea64f7a4cb6ba195c29ab849` | 2026-06-30T20:13:26Z | changelog-worthy | Add connected run query handoff | https://github.com/8Dionysus/aoa-course-connector/pull/59 |
| 60 | `ca2a087b24c87531f18d07813d7432d32c4318c7` | 2026-06-30T20:25:00Z | changelog-worthy | Propagate browser link pattern through connected routes | https://github.com/8Dionysus/aoa-course-connector/pull/60 |
| 61 | `c871f315a773685cfb2592e9bc14749a56f65d9c` | 2026-06-30T20:36:34Z | changelog-worthy | Expose connected run handoff in launch plans | https://github.com/8Dionysus/aoa-course-connector/pull/61 |
| 62 | `dc3c88be9515dba971cdc3010ca22a3243fc612e` | 2026-06-30T20:43:47Z | changelog-worthy | Carry connected run handoff through readiness | https://github.com/8Dionysus/aoa-course-connector/pull/62 |
| 63 | `46359a926e7f1621145c56f45bc3abf55c78e78e` | 2026-06-30T21:10:19Z | changelog-worthy | Fix connected handoff review followups | https://github.com/8Dionysus/aoa-course-connector/pull/63 |
| 64 | `17dfb6457928172f65f1f10714ada08e8405c441` | 2026-06-30T21:58:27Z | changelog-worthy | Record connected run execution options | https://github.com/8Dionysus/aoa-course-connector/pull/64 |
| 65 | `54540be4f25f1135e72ff542af3bf8e1629ba7eb` | 2026-06-30T22:11:42Z | changelog-worthy | [codex] Preserve connected run bounds in readiness | https://github.com/8Dionysus/aoa-course-connector/pull/65 |
| 66 | `a97f91d3c2aa113fc2f72fbcc0b0062fd6b1ab4d` | 2026-06-30T22:21:58Z | changelog-worthy | [codex] Expose MCP commands in connected query handoff | https://github.com/8Dionysus/aoa-course-connector/pull/66 |
| 67 | `f5a69a56e8fa4680254b9cfbd1c34f296fad02e6` | 2026-06-30T22:32:16Z | changelog-worthy | [codex] Classify connected run repair lanes | https://github.com/8Dionysus/aoa-course-connector/pull/67 |
| 68 | `cf84ea1203d73e359ab2feb7a13f8bfe979f1bba` | 2026-06-30T22:43:02Z | changelog-worthy | [codex] Route readiness through connected repair lanes | https://github.com/8Dionysus/aoa-course-connector/pull/68 |
| 69 | `de9e86a8df2bf039762741f160b9097dbab10a5d` | 2026-06-30T22:51:49Z | changelog-worthy | [codex] Expose future platform topology | https://github.com/8Dionysus/aoa-course-connector/pull/69 |
| 70 | `c1107c33a98e60f866a213c390b4bcb1309f918f` | 2026-06-30T23:04:56Z | changelog-worthy | [codex] Add goal audit handoff | https://github.com/8Dionysus/aoa-course-connector/pull/70 |
| 71 | `8a35445a627f12feefa6e1cd01b0cf17d29439ac` | 2026-06-30T23:17:11Z | changelog-worthy | [codex] Expose goal audit through MCP | https://github.com/8Dionysus/aoa-course-connector/pull/71 |
| 72 | `b8d5517d0f1924c6b08bf94315c373554bca1ebc` | 2026-06-30T23:35:23Z | changelog-worthy | [codex] Guard live plans from fixture sources | https://github.com/8Dionysus/aoa-course-connector/pull/72 |
| 73 | `f18bc70df3187b262a16aec28edb78d5045e65f5` | 2026-06-30T23:49:48Z | changelog-worthy | [codex] Scope connected plans to selected sources | https://github.com/8Dionysus/aoa-course-connector/pull/73 |
| 74 | `0d5d578c65adf82c3d3beab88a1b53ec7953fd94` | 2026-07-01T00:01:10Z | changelog-worthy | [codex] Verify browser auth capture origins | https://github.com/8Dionysus/aoa-course-connector/pull/74 |
| 75 | `825d7bb9d25fb5e1e54487a21a020b165d0756d7` | 2026-07-01T00:22:55Z | changelog-worthy | [codex] Add semantic provider preflight | https://github.com/8Dionysus/aoa-course-connector/pull/75 |
| 76 | `f92105781395ec6111765bbcbc41829098ef8c0b` | 2026-07-01T00:31:59Z | changelog-worthy | [codex] Add browser auth host candidates | https://github.com/8Dionysus/aoa-course-connector/pull/76 |
| 77 | `c0b41bf187c4ea684dd495fd9aa45af1413673d7` | 2026-07-01T00:45:34Z | changelog-worthy | [codex] Add goal connection handoff | https://github.com/8Dionysus/aoa-course-connector/pull/77 |
| 78 | `4ba2078710597f6904a46f6d942375944626841d` | 2026-07-01T00:59:21Z | changelog-worthy | [codex] Add connection profile handoff | https://github.com/8Dionysus/aoa-course-connector/pull/78 |
| 79 | `b0e6168aa7a8bb05f214f349b394765c34b9aa84` | 2026-07-01T01:07:52Z | changelog-worthy | [codex] Add connection profile runbook | https://github.com/8Dionysus/aoa-course-connector/pull/79 |
| 80 | `4806afe58ec3546e319b326bb434143d9b9c293d` | 2026-07-01T04:02:27Z | changelog-worthy | [codex] Add connection profile status | https://github.com/8Dionysus/aoa-course-connector/pull/80 |
| 81 | `8b5d0c564b38d2a4abcca3fc36479378235e5f22` | 2026-07-01T04:30:45Z | changelog-worthy | [codex] Preserve connected source scope in readiness | https://github.com/8Dionysus/aoa-course-connector/pull/81 |
| 82 | `d57789f15da13f7ff468ec02303c3c15018c297a` | 2026-07-01T04:35:05Z | changelog-worthy | [codex] Clean connector API surface | https://github.com/8Dionysus/aoa-course-connector/pull/82 |
| 83 | `fe48016a4c17607b511bc1d0d3d8195244557aaf` | 2026-07-01T04:47:25Z | changelog-worthy | Add smoke answer proof quality checks | https://github.com/8Dionysus/aoa-course-connector/pull/83 |
| 84 | `00b77eebc8edaf66683e3c64e3e67254a34415c2` | 2026-07-01T04:52:34Z | changelog-worthy | [codex] Prefer selected semantic provider commands | https://github.com/8Dionysus/aoa-course-connector/pull/84 |
| 85 | `5d32a356db7ce51af41dd9abe1d26a8017539d86` | 2026-07-01T04:55:46Z | changelog-worthy | Guard runtime storage ids | https://github.com/8Dionysus/aoa-course-connector/pull/85 |
| 86 | `e4807809ccd107fbaf65eeca5cfbfe525fcac2a6` | 2026-07-01T05:03:53Z | changelog-worthy | [codex] Require refresh hints for answer quality | https://github.com/8Dionysus/aoa-course-connector/pull/86 |
| 87 | `f758e75da04e7fad802612eee522f18988d14f52` | 2026-07-01T05:03:19Z | changelog-worthy | Enrich answer evidence proof fields | https://github.com/8Dionysus/aoa-course-connector/pull/87 |
| 88 | `183010ff06c572dc5055f6abf83a9cdcb517c589` | 2026-07-01T05:12:14Z | changelog-worthy | [codex] Validate sync run ids before checkpoint writes | https://github.com/8Dionysus/aoa-course-connector/pull/88 |
| 89 | `3dab4e56108e8ca42edd0c65cc4f68aaa32e2f8b` | 2026-07-01T05:17:18Z | changelog-worthy | Omit null optional answer evidence fields | https://github.com/8Dionysus/aoa-course-connector/pull/89 |
| 90 | `a42b63b847b2bb348ee2a51f4112ef70c5aad609` | 2026-07-01T05:17:39Z | changelog-worthy | Add browser snapshot audit | https://github.com/8Dionysus/aoa-course-connector/pull/90 |
| 91 | `f432f1b268d068bc4b2883b854021e95fabac4ea` | 2026-07-01T05:27:47Z | changelog-worthy | Expose browser snapshot audit over MCP | https://github.com/8Dionysus/aoa-course-connector/pull/91 |
| 92 | `41bb8e7e2fb239ff86fa1b08c4d7e4d679a80147` | 2026-07-01T05:41:13Z | changelog-worthy | Embed snapshot audits in browser smoke | https://github.com/8Dionysus/aoa-course-connector/pull/92 |
| 93 | `e4deb70630b65582b0791a28475614521c3bdf36` | 2026-07-01T05:52:40Z | changelog-worthy | Audit page-scoped caption resources | https://github.com/8Dionysus/aoa-course-connector/pull/93 |
| 94 | `c7200e6873f16245bd73455992d0e9557693dc5f` | 2026-07-01T05:54:59Z | changelog-worthy | Surface snapshot audit in connected status | https://github.com/8Dionysus/aoa-course-connector/pull/94 |
| 95 | `a3239fa2d5f04c87960bd01d301e7ab8fff3d051` | 2026-07-07T02:46:35Z | changelog-worthy | Preserve crawl placeholders as discovery evidence | https://github.com/8Dionysus/aoa-course-connector/pull/95 |
| 96 | `ab5a188c9c2b0ac2aaf3c5233d6c79c9d4a9b4a0` | 2026-07-07T02:54:51Z | changelog-worthy | [codex] Expose snippets in evidence packets | https://github.com/8Dionysus/aoa-course-connector/pull/96 |
| 97 | `267905c5700eccfa008a297c186c5d87a61052ee` | 2026-07-07T03:02:50Z | changelog-worthy | [codex] Add graph context to lesson MCP packets | https://github.com/8Dionysus/aoa-course-connector/pull/97 |
| 98 | `2bcaaf067a6bf77ec8125767851c023327f9d235` | 2026-07-07T03:12:56Z | changelog-worthy | [codex] Add CLI lesson context packet | https://github.com/8Dionysus/aoa-course-connector/pull/98 |
| 99 | `206befc3ec46d4ef0fa4743270f45fd71d202c9c` | 2026-07-07T03:20:29Z | changelog-worthy | [codex] Surface lesson context in connected query plans | https://github.com/8Dionysus/aoa-course-connector/pull/99 |
| 100 | `6e1cbd7716fc12dea32d49768a2c8eba9863aba7` | 2026-07-07T03:29:58Z | changelog-worthy | [codex] Add query commands to refresh hints | https://github.com/8Dionysus/aoa-course-connector/pull/100 |
| 101 | `c54ee37c8dfa6cdb42834a6ddcf7687f957900a5` | 2026-07-07T03:39:48Z | changelog-worthy | [codex] Build semantic artifacts during source sync | https://github.com/8Dionysus/aoa-course-connector/pull/101 |
| 102 | `e95a4f6b970dea9502089162f6e119addf39c4fa` | 2026-07-07T03:46:34Z | changelog-worthy | [codex] Make query plan query commands mode aware | https://github.com/8Dionysus/aoa-course-connector/pull/102 |
| 103 | `5768c514e6e31ddebf1230144ddf0890ef85a79e` | 2026-07-07T03:56:14Z | changelog-worthy | Add stable sync identity fingerprints | https://github.com/8Dionysus/aoa-course-connector/pull/103 |
| 104 | `6b37939e7f3a5853d90b0057f94a4d0e4e9267f4` | 2026-07-07T04:05:13Z | changelog-worthy | Add fixture retrieval loop eval | https://github.com/8Dionysus/aoa-course-connector/pull/104 |
| 105 | `60e52071dccb5eaf97eb284758078311c0a7d4ba` | 2026-07-07T04:14:54Z | changelog-worthy | Add connection profile run bridge | https://github.com/8Dionysus/aoa-course-connector/pull/105 |
| 106 | `a5ba293c24fbdf7ad51a63a60697408e78f19f83` | 2026-07-07T04:23:36Z | changelog-worthy | [codex] Add MCP connection profile run plan | https://github.com/8Dionysus/aoa-course-connector/pull/106 |
| 107 | `f8f5318fa0b5a9a73609cf346d42db259569ff67` | 2026-07-07T04:33:06Z | changelog-worthy | [codex] Add answer quality packets | https://github.com/8Dionysus/aoa-course-connector/pull/107 |
| 108 | `a182f1e9b6ce9678b33565062a6ff0f913155f91` | 2026-07-07T04:50:59Z | changelog-worthy | [codex] Add MCP answer packet tool | https://github.com/8Dionysus/aoa-course-connector/pull/108 |
| 109 | `263331e296bf3db613888e1c3ccc5465eb9bac55` | 2026-07-07T04:59:04Z | changelog-worthy | [codex] Add install route eval | https://github.com/8Dionysus/aoa-course-connector/pull/109 |
| 110 | `4f83f7208a68dcb476a54f7f3fe628882e3ae07d` | 2026-07-07T05:07:13Z | changelog-worthy | [codex] Strengthen install route verifier | https://github.com/8Dionysus/aoa-course-connector/pull/110 |
| 111 | `a3e5d9ebb4d9614088bbc23854fdf6d6e2e6d8cd` | 2026-07-07T05:17:28Z | changelog-worthy | [codex] Add MCP connected run execution | https://github.com/8Dionysus/aoa-course-connector/pull/111 |
| 112 | `c5ca58fda7ed0716f6f12ad98aa2dd221ab976f4` | 2026-07-07T05:25:43Z | changelog-worthy | [codex] Expose MCP connected run plan | https://github.com/8Dionysus/aoa-course-connector/pull/112 |
| 113 | `ff395c5db978e10ba277053da54952ec6a86fa04` | 2026-07-07T05:43:31Z | changelog-worthy | Add connected run query packets | https://github.com/8Dionysus/aoa-course-connector/pull/113 |
| 114 | `5e6facd52dea82ac544bd3b99d310627d43a9f09` | 2026-07-07T08:40:58Z | changelog-worthy | Prepare local KAG provider home | https://github.com/8Dionysus/aoa-course-connector/pull/114 |
| 115 | `4f2a79a3bc8b2480dcaa4f07e511ccd98d836237` | 2026-07-07T08:41:23Z | changelog-worthy | [codex] Add preauth readiness gate | https://github.com/8Dionysus/aoa-course-connector/pull/115 |
| 116 | `eabbe1f6fda1e56db8e00af99c98ab1e200d1f23` | 2026-07-07T18:25:16Z | changelog-worthy | [codex] Fix GetCourse live lesson crawl | https://github.com/8Dionysus/aoa-course-connector/pull/116 |
| 117 | `7c25cc1a3cb3856022e4dcd2f4b161fab80bb2bd` | 2026-07-07T18:44:00Z | changelog-worthy | [codex] Preserve browser live source ids | https://github.com/8Dionysus/aoa-course-connector/pull/117 |
| 118 | `28e190a89206069021f7604e0a25be96126c20db` | 2026-07-07T18:59:10Z | changelog-worthy | [codex] Add connected run query matrix | https://github.com/8Dionysus/aoa-course-connector/pull/118 |
| 119 | `86d4764a135a53964adef12fb8b5775da72f6a69` | 2026-07-07T19:19:50Z | changelog-worthy | Handle browser access denied lessons | https://github.com/8Dionysus/aoa-course-connector/pull/119 |
| 120 | `1df6bf33b509a0a75ad759b6fdace6218dec7f1d` | 2026-07-07T19:32:57Z | changelog-worthy | Plan ready subset connected runs | https://github.com/8Dionysus/aoa-course-connector/pull/120 |
| 121 | `f8f71c8d68efa073c5f50e9eff3fab44ff212fba` | 2026-07-07T19:45:49Z | changelog-worthy | Add MCP source catalog | https://github.com/8Dionysus/aoa-course-connector/pull/121 |
| 122 | `bee8214dba145902b9be0aaa8e9e8c78717be755` | 2026-07-07T19:57:00Z | changelog-worthy | Link source catalog to connected runs | https://github.com/8Dionysus/aoa-course-connector/pull/122 |
| 123 | `f94a2c987313303643ed7b28f4c873b87a764b53` | 2026-07-07T20:09:22Z | changelog-worthy | Add MCP source answer route | https://github.com/8Dionysus/aoa-course-connector/pull/123 |
| 124 | `bba0a9ce0d85f15b0eaa69088bc56981b5205619` | 2026-07-07T20:15:38Z | changelog-worthy | Backfill source_answer catalog commands | https://github.com/8Dionysus/aoa-course-connector/pull/124 |
| 125 | `c8f04ffd03def502a9456a1f4a9a9c2c849ea7d3` | 2026-07-07T20:23:06Z | changelog-worthy | Add MCP sources answer aggregation | https://github.com/8Dionysus/aoa-course-connector/pull/125 |
| 126 | `7dd12f5a57bf91a398c6b321d43a3df9dbcd55cd` | 2026-07-07T20:31:59Z | changelog-worthy | Add CLI sources answer route | https://github.com/8Dionysus/aoa-course-connector/pull/126 |
| 127 | `ad3aaa0f7794cac8ee793f01ed3895096698a388` | 2026-07-07T20:39:17Z | changelog-worthy | Surface CLI sources answer in query plans | https://github.com/8Dionysus/aoa-course-connector/pull/127 |
| 128 | `d8fef25f184d666a7481e1e2395ed7f6aa844512` | 2026-07-07T20:50:10Z | changelog-worthy | Prove sources answer in install route | https://github.com/8Dionysus/aoa-course-connector/pull/128 |
| 129 | `f098e8d81a3142159ec182beceadf62e2b13d295` | 2026-07-08T01:15:32Z | changelog-worthy | Return canonical sources list from CLI | https://github.com/8Dionysus/aoa-course-connector/pull/129 |
| 130 | `893726582bc7a366a9470537df8b67bfd83332ed` | 2026-07-08T01:32:47Z | changelog-worthy | [codex] Add sources answer matrix route | https://github.com/8Dionysus/aoa-course-connector/pull/130 |
| 131 | `9fd651573993155526bf7f93e1958bfc9897bd3b` | 2026-07-08T02:12:35Z | changelog-worthy | [codex] Teach readiness source-registry query state | https://github.com/8Dionysus/aoa-course-connector/pull/131 |
| 132 | `7e4168b9668fac6553786113a83f264c086119ab` | 2026-07-08T02:12:37Z | changelog-worthy | [codex] Backfill repo-local KAG substrate | https://github.com/8Dionysus/aoa-course-connector/pull/132 |
| 133 | `db322cd1d36d0eefa7c4796e84f918d256020ae0` | 2026-07-08T02:24:08Z | changelog-worthy | [codex] Add source registry query eval | https://github.com/8Dionysus/aoa-course-connector/pull/133 |
| 134 | `3668866e9f8aef0e06639a463bd80529d38fb638` | 2026-07-08T02:44:56Z | changelog-worthy | [codex] Add Stepik browser-state auth route | https://github.com/8Dionysus/aoa-course-connector/pull/134 |
| 135 | `ac1233a8de759556093c3f76d43c6ee96bd83660` | 2026-07-08T02:47:58Z | changelog-worthy | [codex] Refresh KAG index after Stepik browser auth | https://github.com/8Dionysus/aoa-course-connector/pull/135 |
| 136 | `454da73d3fa32b050e1630c916f53bf8b381fd68` | 2026-07-08T07:48:33Z | changelog-worthy | Add Firefox Stepik browser state import | https://github.com/8Dionysus/aoa-course-connector/pull/136 |
| 137 | `f642d9567fdd4e6075a8718f88e42c44074ea9cc` | 2026-07-08T07:50:39Z | generated churn | Refresh KAG index after Firefox Stepik import | https://github.com/8Dionysus/aoa-course-connector/pull/137 |
| 138 | `bf2d34c737cbedad4aebffde02e3e37a5920a21c` | 2026-07-08T08:02:22Z | changelog-worthy | Use Stepik grades and sync checkpoints for source queries | https://github.com/8Dionysus/aoa-course-connector/pull/138 |
| 139 | `6829ffb2bc9e332c172bb530d41087074b2edd5c` | 2026-07-08T08:03:57Z | generated churn | Refresh KAG index after Stepik grades discovery | https://github.com/8Dionysus/aoa-course-connector/pull/139 |
| 140 | `efa787efab8d11d0dd787d2ef6ba3d4b7a858868` | 2026-07-08T08:19:30Z | changelog-worthy | Add GetCourse Chatium catalog discovery | https://github.com/8Dionysus/aoa-course-connector/pull/140 |
| 141 | `09033b7b01fbb2524aa75b3544894d6970555dba` | 2026-07-08T08:33:14Z | changelog-worthy | Add portfolio coverage mode for source matrices | https://github.com/8Dionysus/aoa-course-connector/pull/141 |
| 142 | `3415829a4a273cccb8efe691779d12167c909ef5` | 2026-07-08T08:50:16Z | changelog-worthy | [codex] Add materialize content counts | https://github.com/8Dionysus/aoa-course-connector/pull/142 |
| 143 | `2e9c76368fd4caa4e686231691454be2af6f6c5b` | 2026-07-08T08:57:35Z | changelog-worthy | [codex] Document multisource live proof | https://github.com/8Dionysus/aoa-course-connector/pull/143 |
| 144 | `eb750d07eb3007889d7ac423e5b0a9f0ddb7a2f2` | 2026-07-08T09:10:51Z | changelog-worthy | [codex] Expose browser Firefox import plan | https://github.com/8Dionysus/aoa-course-connector/pull/144 |
| 145 | `75e70793103903b726b06b2eaf2b05fc237d3218` | 2026-07-08T09:17:43Z | changelog-worthy | [codex] Expose profile Firefox import route | https://github.com/8Dionysus/aoa-course-connector/pull/145 |
| 146 | `8a1cc5bd2bad57e1504e8626e2f2ced304403cd9` | 2026-07-08T15:54:31Z | changelog-worthy | [codex] Reuse Stepik sync for live smoke | https://github.com/8Dionysus/aoa-course-connector/pull/146 |
| 147 | `2cc6814eec3c9bef9c602b55828d751834df6cf0` | 2026-07-08T16:12:56Z | changelog-worthy | [codex] Propagate Stepik enrichment budget through agent plans | https://github.com/8Dionysus/aoa-course-connector/pull/147 |
| 148 | `6c726b4ee8567b9bcd8a19e3622d847b2fd5aaf5` | 2026-07-08T16:20:50Z | changelog-worthy | [codex] Preserve Stepik repair budget | https://github.com/8Dionysus/aoa-course-connector/pull/148 |
| 149 | `329fb2c480475d5140c8b16f423cae9164fec48e` | 2026-07-08T17:02:50Z | changelog-worthy | [codex] Remove course runbook overcode | https://github.com/8Dionysus/aoa-course-connector/pull/149 |
| 150 | `bdad76126388d755ea8975ded60ce3dacfeedb4a` | 2026-07-08T17:37:10Z | changelog-worthy | [codex] Add fresh-local-grounded retrieval quality | https://github.com/8Dionysus/aoa-course-connector/pull/150 |
| 151 | `7e076807d570f2765c7f4dbca686305262f68d64` | 2026-07-08T17:52:05Z | changelog-worthy | [codex] Normalize Firefox cookie expiry for Playwright | https://github.com/8Dionysus/aoa-course-connector/pull/151 |
| 152 | `6f73877c4a5e4b9ccee527f5713023cac2671961` | 2026-07-08T18:03:17Z | changelog-worthy | Add place-aware retrieval quality eval | https://github.com/8Dionysus/aoa-course-connector/pull/152 |
| 153 | `d4899df6592678e77c647f5bf294b46b1ba3517a` | 2026-07-08T18:17:43Z | changelog-worthy | Add grounded portfolio quality for source answers | https://github.com/8Dionysus/aoa-course-connector/pull/153 |
| 154 | `7c0632bcc025a62b6b4a00a918d0e81736f1d2c4` | 2026-07-08T18:29:33Z | changelog-worthy | Add intent-gated temporal retrieval eval | https://github.com/8Dionysus/aoa-course-connector/pull/154 |
| 155 | `1d6deaa8024b7069b77c84b6d4468794f81fa18f` | 2026-07-08T18:38:41Z | changelog-worthy | Capture Skillspace API catalog discovery | https://github.com/8Dionysus/aoa-course-connector/pull/155 |
| 156 | `8addfa3df76015f051e74175c06bc36aead1d727` | 2026-07-08T18:49:53Z | changelog-worthy | Tighten source answer readiness contract | https://github.com/8Dionysus/aoa-course-connector/pull/156 |
| 157 | `cca5c2912a99af3c7460281304df3ae8c67f7ce5` | 2026-07-08T19:00:07Z | generated churn | Refresh course connector KAG source index | https://github.com/8Dionysus/aoa-course-connector/pull/157 |
| 158 | `536f7202ae7d80dc1e5065cd08dc38841800f81e` | 2026-07-08T19:08:08Z | changelog-worthy | Harden fresh-local-grounded retrieval quality | https://github.com/8Dionysus/aoa-course-connector/pull/158 |
| 159 | `f2781fec264f56e9bbb3d7870ec2f4077911a9b8` | 2026-07-08T19:13:31Z | changelog-worthy | Fix connector review regressions | https://github.com/8Dionysus/aoa-course-connector/pull/159 |
| 160 | `e0633f59c3268d714caee211ba393e736438fdde` | 2026-07-08T23:08:43Z | changelog-worthy | Fix older course connector review regressions | https://github.com/8Dionysus/aoa-course-connector/pull/160 |
| 161 | `e4d140a4d1e5a0247aede16a9d0e815f59ea9c09` | 2026-07-08T23:19:23Z | changelog-worthy | Fix symbolic course token retrieval | https://github.com/8Dionysus/aoa-course-connector/pull/161 |
| 162 | `fb080273838bcbb03dedf65f7ce169f6fff56010` | 2026-07-08T23:23:30Z | changelog-worthy | Clean portfolio source answer summaries | https://github.com/8Dionysus/aoa-course-connector/pull/162 |
| 163 | `4752c840f7640ef8730b8ddcfdd7fd139a3ac8d4` | 2026-07-08T23:29:59Z | changelog-worthy | Expose sync coverage counts in source catalog | https://github.com/8Dionysus/aoa-course-connector/pull/163 |
| 164 | `ef75fd3c1732c2ee2a1bfc657f38e91e37d9b874` | 2026-07-08T23:33:26Z | generated churn | Refresh course connector KAG source index | https://github.com/8Dionysus/aoa-course-connector/pull/164 |
| 165 | `380308bfb27834d76f37e257ee156037388951c7` | 2026-07-08T23:37:59Z | changelog-worthy | Fix course connector follow-up review issues | https://github.com/8Dionysus/aoa-course-connector/pull/165 |
| 166 | `fca4c0f50e7e455b15351bb46de0b030d2511a94` | 2026-07-08T23:56:00Z | changelog-worthy | Improve portfolio ranking and source catalog status | https://github.com/8Dionysus/aoa-course-connector/pull/166 |
| 167 | `ac5fa648602e0411c16aa1c3ae34a8f9a6dbde5e` | 2026-07-09T00:05:25Z | generated churn | Refresh course connector KAG source index | https://github.com/8Dionysus/aoa-course-connector/pull/167 |
| 168 | `0c1d4dfb1fdcd8b01a172c4b6f19361ec0bbd4cf` | 2026-07-09T00:16:39Z | changelog-worthy | Block external semantic providers by path alias | https://github.com/8Dionysus/aoa-course-connector/pull/168 |
| 169 | `67944a0f85d02e5332ce17a63bb3a13948e23ae2` | 2026-07-09T00:27:37Z | changelog-worthy | Harden source answer readiness contracts | https://github.com/8Dionysus/aoa-course-connector/pull/169 |
| 170 | `feba995f1caea9dcd83291a2027212608257c05b` | 2026-07-09T00:57:18Z | changelog-worthy | Fix course source answer review follow-ups | https://github.com/8Dionysus/aoa-course-connector/pull/170 |
| 171 | `7551c58f461dcd76c2ba98ecd2e012967148c427` | 2026-07-09T01:11:05Z | changelog-worthy | Fix browser audit and KAG manifest validation | https://github.com/8Dionysus/aoa-course-connector/pull/171 |
| 172 | `10e1ae1f2d4b3f1ca7526938e1ee160b4bf8091e` | 2026-07-09T02:15:50Z | changelog-worthy | Harden course connector review contracts | https://github.com/8Dionysus/aoa-course-connector/pull/172 |
| 173 | `96f370af0c5b880d1e9932716d9bd94e6906ac97` | 2026-07-10T01:47:24Z | changelog-worthy | Add connected portfolio retrieval quality gate | https://github.com/8Dionysus/aoa-course-connector/pull/173 |
| 174 | `21c489709f431d6103262abd2e83d184bc4461ea` | 2026-07-10T02:26:43Z | changelog-worthy | Add ingest completeness and refresh continuity gates | https://github.com/8Dionysus/aoa-course-connector/pull/174 |
| 175 | `2919ce3795dca2c896071ec7d06eac9442b0643b` | 2026-07-10T03:07:35Z | changelog-worthy | Add corpus integrity and retrieval recall gate | https://github.com/8Dionysus/aoa-course-connector/pull/175 |
| 176 | `f9f4be7c6934f9670439ab03db1baf8393b9ee0b` | 2026-07-10T03:23:49Z | changelog-worthy | Enforce repo-local KAG index parity | https://github.com/8Dionysus/aoa-course-connector/pull/176 |
| 177 | `a4e2d93f4189e3d2d83cc8dd4ef15acca5a12526` | 2026-07-10T03:58:15Z | changelog-worthy | Implement versioned BM25 retrieval | https://github.com/8Dionysus/aoa-course-connector/pull/177 |
| 178 | `64a36becd3851c23bb2829dc0eb936dc9b9d3f47` | 2026-07-10T07:00:21Z | changelog-worthy | Pin deterministic repo-local KAG index gate | https://github.com/8Dionysus/aoa-course-connector/pull/178 |
| 179 | `a1038187f16669cccdc7663d3fb239c9c432d8fe` | 2026-07-10T05:34:38Z | changelog-worthy | Sanitize the public connector seed | https://github.com/8Dionysus/aoa-course-connector/pull/179 |
| 180 | `2553848e089fc143957a6133f7babe04ed573415` | 2026-07-11T05:08:57Z | changelog-worthy | Add repository KAG index family | https://github.com/8Dionysus/aoa-course-connector/pull/180 |
| 181 | `948315ca430d575e40ed49be788e7bfbab6a7602` | 2026-07-13T13:47:33Z | changelog-worthy | Publish canonical repository KAG indexes | https://github.com/8Dionysus/aoa-course-connector/pull/181 |
| 182 | `10c7e75707cea43ee493496f005b4b6ceeab7281` | 2026-07-14T12:39:39Z | changelog-worthy | Add course connector local stats port | https://github.com/8Dionysus/aoa-course-connector/pull/182 |
| 183 | `346254a134f6f7dd14c6edc0a519a2681d8813a9` | 2026-07-17T19:55:02Z | changelog-worthy | Adopt portable KAG index family | https://github.com/8Dionysus/aoa-course-connector/pull/183 |
| 184 | `3f322cbd5c874744f29039b560044641862a7822` | 2026-07-26T18:12:02Z | changelog-worthy | Make Course eval and release scenarios owner-driven | https://github.com/8Dionysus/aoa-course-connector/pull/184 |
| 185 | `5a5219ef027df029313fc527c71a8764cfbd193e` | 2026-07-29T06:10:00Z | changelog-worthy | Require an explicit Course owner root for MCP | https://github.com/8Dionysus/aoa-course-connector/pull/185 |
| 186 | `d9f414cc51ae60c0d78a3bbbb176ecac179afeac` | 2026-08-10T21:49:13Z | changelog-worthy | Pin accepted aoa-kag owner-family DAG | https://github.com/8Dionysus/aoa-course-connector/pull/186 |

Review of the four release-boundary PRs:

- **#183** is a separate changelog-worthy artifact/consumer contract. Its large generated diff is not noise because the portable family, digest, compatibility view, and CI admission behavior changed.
- **#184** is a separate changelog-worthy release-process/eval contract. Its 43 scenarios are generated from owner inputs but the executable generator and subprocess validation are source behavior.
- **#185** is a separate changelog-worthy authority and compatibility change. It requires an explicit owner root and is the only release item with a direct caller migration posture.
- **#186** is a separate changelog-worthy dependency/admission change with generated churn. The landed workflow ref, not the PR-body narrative ref, is authoritative.


## 12. Non-first-parent side-commit ledger

The following 64 commits are reachable from current main but not on its first-parent spine. They are classified as side material combined into the merged PR carrier, generated churn, duplicate merge plumbing, or internal/noise; none is treated as an independent release baseline.

| Commit | Date | Classification | Subject |
|---|---|---|---|
| `ec1d27867a2ec1d52eacac58e0278c82773f3d2c` | 2026-07-09 | duplicate | Merge remote-tracking branch 'origin/main' into codex/bm25-retrieval |
| `ffaafbe03b443a383a4c52df8848e990c99f396e` | 2026-07-09 | generated churn | Refresh generated source surface index |
| `6be1b1a3820b4bab63c30a907994d15b33341bfe` | 2026-07-09 | combined with merged PR | Implement versioned BM25 retrieval |
| `a31a2f26de815f210261b02211abd5ce8bbd462e` | 2026-07-09 | combined with merged PR | Make CI fixture bootstrap explicit |
| `284eb947dc582b6fe2c470d00331136b949ce8b5` | 2026-07-09 | combined with merged PR | Add corpus integrity and retrieval recall gate |
| `50cd292bccaef77d221de91642df9c230034bd7b` | 2026-07-09 | generated churn | Add ingest completeness and refresh continuity gates |
| `73381d52aa565c442c4ccb064e32948683e98f55` | 2026-07-09 | combined with merged PR | Add connected portfolio retrieval quality gate |
| `672a171cf6f90e603216dbae188f0412ebd403fc` | 2026-07-08 | combined with merged PR | Fix browser crawl audit and KAG manifest validation |
| `3e131c7fb90f3ac77543e1fa20f9736e601d261d` | 2026-07-08 | combined with merged PR | Remove course runbook overcode |
| `1757de7d5fe857db680b2cf54dc2a15aae5f0528` | 2026-07-08 | combined with merged PR | Preserve Stepik repair budget |
| `9ea03e576485ef57739f7fd3d56337566aa8d1b7` | 2026-07-08 | combined with merged PR | Propagate Stepik enrichment budget through agent plans |
| `91875c8ab91a7d5ebd3a7ed573b593c6da12ab43` | 2026-07-08 | combined with merged PR | Add portfolio coverage mode for source matrices |
| `e33f61991b13f2a19d1bccbfe2eb4ac103031c5b` | 2026-07-08 | combined with merged PR | Add GetCourse Chatium catalog discovery |
| `0bd80c47af73e06dbe51886258ef6518f2865f27` | 2026-07-08 | generated churn | Refresh KAG index after Stepik grades discovery |
| `1dacd9a06ed4d1b0ffbf1e274c8a85b2817699bb` | 2026-07-08 | combined with merged PR | Use Stepik grades and sync checkpoints for source queries |
| `15816af04fb058643fd29d704db141fbd23a5434` | 2026-07-08 | generated churn | Refresh KAG index after Firefox Stepik import |
| `f6b69d1dfff7cd38abb827f13758690fa8dbebdb` | 2026-07-08 | combined with merged PR | Add Firefox Stepik browser state import |
| `0558d060e80266aad3f755fdc3b0eb48a596d39c` | 2026-07-07 | generated churn | Refresh KAG index after Stepik browser auth |
| `915ebacf185f08d1ecf1195b69b472c4d850421b` | 2026-07-07 | combined with merged PR | Add Stepik browser state auth route |
| `f25d9fd70af9c25dd5a8cb345c91940d3cb51c0e` | 2026-07-07 | combined with merged PR | Add source registry query eval |
| `449ad3b50e4f959715454c16a794605d4c39373d` | 2026-07-07 | combined with merged PR | Teach readiness source-registry query state |
| `7e4168b9668fac6553786113a83f264c086119ab` | 2026-07-07 | combined with merged PR | Backfill live KAG source surface index |
| `b1c92f30628b80ed954985b1d3c2c8fd3a38a405` | 2026-07-07 | combined with merged PR | Add sources answer matrix route |
| `041c50301c0ff080040c21490f91be3c878d7078` | 2026-07-07 | combined with merged PR | Return canonical sources list from CLI |
| `1c66e8499fbad782c7b44906f101bb924a1a51b8` | 2026-07-07 | combined with merged PR | Prove sources answer in install route |
| `9d7372504c56aeb0b3ebdf93c3ff35dd98cfadce` | 2026-07-07 | combined with merged PR | Surface CLI sources answer in query plans |
| `ecfddb9c208021eb0d03735eafe1060f658464f5` | 2026-07-07 | combined with merged PR | Add CLI sources answer route |
| `65a44f43037dede1046e8e8daa5e241e3253a92a` | 2026-07-07 | combined with merged PR | Add MCP sources answer aggregation |
| `e56458f24ee1ab5a5bdeb6f2047f3df93b9b2599` | 2026-07-07 | combined with merged PR | Backfill source_answer catalog commands |
| `65d4ec267e0ee51f08907546ea87509795409ab2` | 2026-07-07 | combined with merged PR | Add MCP source answer route |
| `cde88e25192b1e31860f8454e2e4e74b2f6a28c0` | 2026-07-07 | combined with merged PR | Link source catalog to connected runs |
| `95aaa5cd873f8c36837a01c34773e37f28d2e0cb` | 2026-07-07 | combined with merged PR | Add MCP source catalog |
| `dd291e0fdb65847df901b78e945b7be376588c76` | 2026-07-07 | combined with merged PR | Plan ready subset connected runs |
| `f508069b6d12993e431cc5442c032043a6c48ca8` | 2026-07-07 | combined with merged PR | Handle browser access denied lessons |
| `e07ece9b356d723076f6ff9cf23451ffa8bf2483` | 2026-07-07 | combined with merged PR | Add connected run query matrix |
| `ae90a8cf015ddbe3a8b60dc9d121233b5eb9d653` | 2026-07-07 | combined with merged PR | Preserve browser live source ids |
| `c87e553e4efa6f8455c75ec5cdcdb49b4fb7fa9b` | 2026-07-07 | combined with merged PR | Fix GetCourse live lesson crawl |
| `c022b40b2bcd2636e5e81b41f340982058982124` | 2026-07-07 | combined with merged PR | Prepare local KAG provider home |
| `f4b5f56388dd381f7618172ce408dd1a3182d9aa` | 2026-07-07 | combined with merged PR | Add preauth readiness gate |
| `90931789ec70a149dca2ec59f7d400c509b17652` | 2026-07-06 | combined with merged PR | Add connected run query packets |
| `f0a2660a356ab9541755ea36d82766eab3d788b0` | 2026-07-06 | combined with merged PR | Expose MCP connected run plan |
| `4f1a848e28506900dbcb0b26e59161384221272d` | 2026-07-06 | combined with merged PR | Add MCP connected run execution |
| `e7725377ce5186898124897faf3badc6e75a344f` | 2026-07-06 | combined with merged PR | Strengthen install route verifier |
| `1c741f6f8a9709c4667e0afa924a1e1b90c1c40c` | 2026-07-06 | combined with merged PR | Add install route eval |
| `754ec431eb8c4d8546b9d9e6a85918f44b3c5d62` | 2026-07-06 | combined with merged PR | Add MCP answer packet tool |
| `89af48ec123226a77bfa0f65caf238fc2dba115c` | 2026-07-06 | combined with merged PR | Add answer quality packets |
| `dc0d2e04ece9dd4495fdbc18833adeda1f1610fb` | 2026-07-06 | combined with merged PR | Add MCP connection profile run plan |
| `791e79597355b27b5b95d0dad46e8d721f80b220` | 2026-07-06 | combined with merged PR | Add connection profile run bridge |
| `3dbde8f12346c80f09c2afbd577d180d36466d6e` | 2026-07-06 | combined with merged PR | Add fixture retrieval loop eval |
| `5ffe42947489959489aa29936409ae4cebb67d6e` | 2026-07-06 | combined with merged PR | Add stable sync identity fingerprints |
| `fef652c7b06d9df4963ab3bb279a95501151e077` | 2026-07-06 | combined with merged PR | Make query plan query commands mode aware |
| `9a75ad9319b8c712143e972d50f204adfca62e32` | 2026-07-06 | combined with merged PR | Build semantic artifacts during source sync |
| `afdce2c7ea3552559fe90f5f84aa64d028bdf194` | 2026-07-06 | generated churn | Add query commands to refresh hints |
| `396662c05a157393323a6c10980ab7ff8dad1ef3` | 2026-07-06 | combined with merged PR | Surface lesson context in connected query plans |
| `29425373a4fb6a4a58968854d74edf8d4297ac21` | 2026-07-06 | combined with merged PR | Add CLI lesson context packet |
| `8eaf62b4a4f014f672176b2028067b776cad369f` | 2026-07-06 | combined with merged PR | Add graph context to lesson MCP packets |
| `ddb65f714f20bcc1fdab790147beb39129dc0feb` | 2026-07-06 | combined with merged PR | Expose snippets in evidence packets |
| `04667ce5db35a665879f098f912b2053877cc94f` | 2026-07-06 | combined with merged PR | Preserve crawl placeholders as discovery evidence |
| `73e4b6195a5e984d41ab06a9d450a901689ad55f` | 2026-06-30 | combined with merged PR | Surface snapshot audit in connected status |
| `faa310f62eae59ffb4575d07d13d7fe0171d0ae1` | 2026-06-30 | combined with merged PR | Embed snapshot audits in browser smoke |
| `9a28da4c08c30e971c418302f26e71e89491337f` | 2026-06-30 | combined with merged PR | Expose browser snapshot audit over MCP |
| `3dd5dec63cce09a7e270a6f85a79d2353ae0259d` | 2026-06-30 | combined with merged PR | Add browser snapshot audit |
| `f9555ec3b27a785674e34e1eea6c9466376e9c31` | 2026-06-30 | generated churn | Require refresh hints for answer quality |
| `5d6916abd192aa260f79a7f645b8b46aa4f10b14` | 2026-06-30 | combined with merged PR | Prefer selected semantic provider commands |

Exact command used to establish the full side set: `git log --format='%H%x09%ad%x09%s' --date=iso-strict main` minus the hashes returned by `git log --first-parent ... main`.


## 13. Dependency reconciliation for the published release

The provider-before-consumer gate was rechecked after Wave 1. The exact
stable published provider tags resolve as follows:

| Provider | Published tag | Resolved commit | Consumer surface |
|---|---|---|---|
| `8Dionysus/aoa-kag` | `v0.5.0` | `813a7f69dc96ec031dad9b897a6991792cc48b7a` | repo-local KAG action and owner-family admission |
| `8Dionysus/aoa-stats` | `v0.2.0` | `dc608fd5de3fcaf0301f356c9efd52e2bdd350ce` | direct validation checkout and local stats-port contract |

The KAG action ref in the workflow remains `6a79e62c7d20b6b11406dee78f409ada4a51bb3f`, the accepted helper pin from landed #186. It is not substituted for the provider release tag; the distinction is recorded in the manifest and changelog. No `aoa-session-memory` ref, tag, Release, or archived `aoa-routing`/`abyss-stack_old` surface was touched.

The independent `abyss-stack` consumer, central `aoa-evals` proof, shared
`aoa-stats` federation, and human acceptance remain downstream owner
boundaries. This source release does not claim their completion.
