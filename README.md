# Lunar Site Scout

Terrain-aware lunar south pole landing site planner. Compare sites and dates for sunlight and direct-to-Earth communications using LOLA topography and JPL ephemerides.

> Built for the 2026 NASA Space Apps Challenge (Lunar Landing Site Navigator). Not affiliated with or endorsed by NASA.

## Data sources

Every dataset the tool uses or plans to use is listed in the dataset registry, [`lss/registry/datasets.yaml`](lss/registry/datasets.yaml). Each entry gives coverage, resolution, what the dataset can and cannot answer, its citation and its license. The API will serve the same list at `GET /api/datasets`.

Methodology: [`docs/methodology.md`](docs/methodology.md).

## AI usage

_Stub. Completed before submission._

This project was built with SI (AI) assistance from Claude (Anthropic). The concept and features are the author's. Claude assisted with design, implementation, debugging and data research, and the author reviewed its output. Source files written with Claude carry a header saying so.

## License

Apache-2.0. See [LICENSE](LICENSE).
