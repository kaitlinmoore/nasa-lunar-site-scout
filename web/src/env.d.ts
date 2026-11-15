// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
/// <reference types="vite/client" />

declare const __CONTRACT_VERSION__: string
/** Contract field descriptions, { SchemaName: { field: description } }, from fixtures/openapi.json. */
declare const __FIELD_DOCS__: Record<string, Record<string, string>>

interface ImportMetaEnv {
  readonly VITE_API_BASE?: string
  readonly VITE_CESIUM_ION_TOKEN: string
  /** Default data source when the URL has no ?source=: "live" (default) or "fixtures". */
  readonly VITE_DATA_SOURCE?: string
}
