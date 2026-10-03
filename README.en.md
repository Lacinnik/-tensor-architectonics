# Tensor Architectonics (TzAr)

*English summary. The full, authoritative documentation is in Russian: [README.md](README.md).*

Research repository of Tensor Architectonics — an authorial system by Alexander Latsinnik. The corpus is organised by level, and every document carries an explicit status (`canonical` or `candidate`).

| Folder | Contents |
|---|---|
| [`01-declarations`](01-declarations/) | declarations — the source statements of the system |
| [`02-axioms`](02-axioms/) | axioms and invariants |
| [`03-theory`](03-theory/) | theorems and models |
| [`04-mathematical-apparatus`](04-mathematical-apparatus/) | formalisation |
| [`05-engineering-applications`](05-engineering-applications/) | engineering checks and experiments |
| [`contour/manifest.json`](contour/manifest.json) | machine-readable map of the corpus |

Terms such as "tensor", "theorem" or "quantum engine" are used in the author's own sense inside this system; they are not claims of peer-reviewed physics or mathematics.

Key terms with their canonical (Russian) definitions: [GLOSSARY.md](GLOSSARY.md).

## Products

| Product | Version | Status |
|---|---|---|
| [TZAR Conductance](products/tzar-conductance/) — local model assessment of free-form statements, with signed passports | 1.0.0 | stable |
| [Ego Interface](products/tzar-conductance/ego-interface/) | 0.2.0-candidate | candidate |
| [Supra XR Cosmos Portal](products/tzar-conductance/supra-cosmos/) | 0.4.0-candidate | candidate |
| [QENGINE](05-engineering-applications/QENGINE-001/) — six author engines | 0.2.0 | candidate, author-reviewed |
| TZAR-LANGUAGE-001 — deterministic symbolic language compiler (not a trained neural model) | 0.2 | candidate |

Live platform: https://lacinnik.github.io/-tensor-architectonics/ · Machine-readable statuses: [`ecosystem.status.json`](ecosystem.status.json).

## Citing

See [`CITATION.cff`](CITATION.cff). [`.zenodo.json`](.zenodo.json) holds the metadata for archiving releases on Zenodo with a DOI.

## Ecosystem

The single entry point to all products is [Platform 2.0](https://lacinnik.github.io/Game-GDEYA/platform/). Related repositories: [architectonica-az-buki](https://github.com/Lacinnik/architectonica-az-buki) (source corpus and cores), [reason-](https://github.com/Lacinnik/reason-) (REZON lab), [Game-GDEYA](https://github.com/Lacinnik/Game-GDEYA) (game and platform).

## License

[MIT](LICENSE).
