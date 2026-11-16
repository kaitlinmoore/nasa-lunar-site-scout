// SI-assisted: generated with Claude (Anthropic) and reviewed by the project author. See README "AI usage".
// The server's scenario key (lss/contract/models.py `Scenario.key()`), for matching a comparison's
// results to its columns: CompareResponse.compared lists Scenarios without keys, while items,
// not_served, filtered_out, evaluated and rank_ties refer to scenarios by key. Callers must check the
// keys they compute against the keys the API sends (mapComparison does) and refuse on any mismatch.
//
// Scenario.key() = first 16 hex digits of SHA-256 of
//   json.dumps(scenario.model_dump(mode="json", exclude={"location": {"name"}}), sort_keys=True,
//              separators=(",", ":"))
// The dates and the step are used exactly as the API sent them (they are its own JSON serialisation);
// numbers are written the way Python writes a float. Pure and synchronous, so it runs in Node tests.
import type { components } from './schema'

type Scenario = components['schemas']['Scenario']

/** Python's repr() of a float (shortest round-trip digits, as JavaScript, but in Python's notation). */
export function pyFloat(x: number): string {
  if (!Number.isFinite(x)) throw new Error(`no JSON form for ${x}`)
  if (Object.is(x, -0)) return '-0.0'
  const abs = Math.abs(x)
  if (abs !== 0 && (abs < 1e-4 || abs >= 1e16)) {
    // Python: scientific, at least two exponent digits ("1e-05", "1.5e+16").
    const [mantissa, exp] = x.toExponential().split('e')
    const e = Number(exp)
    return `${mantissa}e${e < 0 ? '-' : '+'}${String(Math.abs(e)).padStart(2, '0')}`
  }
  const s = String(x)
  return Number.isInteger(x) ? `${s}.0` : s
}

/** The canonical JSON the server hashes. */
export function canonicalScenario(s: Scenario): string {
  const str = (v: string) => JSON.stringify(v)
  // Keys in sorted order, as sort_keys=True: location{lat, lon}, step, unit_height_m, window_end, window_start.
  return (
    `{"location":{"lat":${pyFloat(s.location.lat)},"lon":${pyFloat(s.location.lon)}},` +
    `"step":${str(s.step ?? 'PT1H')},"unit_height_m":${pyFloat(s.unit_height_m)},` +
    `"window_end":${str(s.window_end)},"window_start":${str(s.window_start)}}`
  )
}

// SHA-256 (FIPS 180-4), small and synchronous.
const K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5, 0xd807aa98,
  0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786,
  0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8,
  0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
  0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819,
  0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a,
  0x5b9cca4f, 0x682e6ff3, 0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
])

export function sha256Hex(text: string): string {
  const data = new TextEncoder().encode(text)
  const bitLen = data.length * 8
  const padded = new Uint8Array((((data.length + 9 + 63) >> 6) << 6) >>> 0)
  padded.set(data)
  padded[data.length] = 0x80
  const view = new DataView(padded.buffer)
  view.setUint32(padded.length - 8, Math.floor(bitLen / 2 ** 32))
  view.setUint32(padded.length - 4, bitLen >>> 0)
  const h = new Uint32Array([
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19,
  ])
  const w = new Uint32Array(64)
  const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n))
  for (let off = 0; off < padded.length; off += 64) {
    for (let i = 0; i < 16; i++) w[i] = view.getUint32(off + 4 * i)
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3)
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10)
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0
    }
    let [a, b, c, d, e, f, g, hh] = h
    for (let i = 0; i < 64; i++) {
      const t1 = (hh + (rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i]) >>> 0
      const t2 = ((rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)) + ((a & b) ^ (a & c) ^ (b & c))) >>> 0
      hh = g
      g = f
      f = e
      e = (d + t1) >>> 0
      d = c
      c = b
      b = a
      a = (t1 + t2) >>> 0
    }
    h[0] += a
    h[1] += b
    h[2] += c
    h[3] += d
    h[4] += e
    h[5] += f
    h[6] += g
    h[7] += hh
  }
  return [...h].map((x) => x.toString(16).padStart(8, '0')).join('')
}

/** The server's Scenario.key() for a scenario as the API sent it. */
export function scenarioKey(s: Scenario): string {
  return sha256Hex(canonicalScenario(s)).slice(0, 16)
}
