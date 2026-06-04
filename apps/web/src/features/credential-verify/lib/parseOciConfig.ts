/**
 * Parser for the OCI CLI config file (the ini block the Oracle console hands
 * out under "API Keys → Add API Key → Configuration File Preview").
 *
 * Example input:
 *
 *   [DEFAULT]
 *   user=ocid1.user.oc1..aaa...
 *   fingerprint=2a:69:...
 *   tenancy=ocid1.tenancy.oc1..aaa...
 *   region=ap-chuncheon-1
 *   key_file=<path>   # the private key is uploaded separately
 *
 * The parser is a pure function (no DOM, no network) so it is trivially unit
 * tested. It is intentionally lenient: it ignores blank lines, comments
 * (`#`/`;`), the `[SECTION]` header, and the `key_file` line, and tolerates
 * surrounding whitespace. Only the four fields the credential form can prefill
 * are returned; `key_file` is reported via `keyFileIgnored` so the UI can show
 * the "upload the key below" hint.
 */

export interface ParsedOciConfig {
  /** Maps to the form's `tenancy_ocid` field. */
  tenancy_ocid?: string;
  /** Maps to the form's `user_ocid` field. */
  user_ocid?: string;
  fingerprint?: string;
  region?: string;
}

export interface ParseOciConfigResult {
  /** The fields that were successfully extracted (only present keys). */
  fields: ParsedOciConfig;
  /** A `key_file=` line was present and intentionally skipped. */
  keyFileIgnored: boolean;
  /** Recognised keys that produced a value (for "filled N fields" feedback). */
  matchedKeys: Array<keyof ParsedOciConfig>;
}

/** ini key → form field. `tenancy`/`user` are the OCI names; we map to *_ocid. */
const KEY_MAP: Record<string, keyof ParsedOciConfig> = {
  tenancy: "tenancy_ocid",
  user: "user_ocid",
  fingerprint: "fingerprint",
  region: "region",
};

/** Strip a trailing inline comment (` # ...` or ` ; ...`) from a value. */
function stripInlineComment(value: string): string {
  // Only treat # / ; as a comment when preceded by whitespace so values that
  // legitimately contain them aren't truncated (OCIDs / fingerprints don't,
  // but be conservative).
  const match = value.match(/^(.*?)\s+[#;].*$/);
  return (match ? match[1] : value).trim();
}

/**
 * Parse an OCI config ini block. Always returns a result (never throws); an
 * input with no recognised keys yields empty `fields` and `matchedKeys`.
 */
export function parseOciConfig(input: string): ParseOciConfigResult {
  const fields: ParsedOciConfig = {};
  const matchedKeys: Array<keyof ParsedOciConfig> = [];
  let keyFileIgnored = false;

  for (const rawLine of input.split(/\r?\n/)) {
    const line = rawLine.trim();
    // Skip blanks, full-line comments, and the [SECTION] header.
    if (line === "" || line.startsWith("#") || line.startsWith(";")) continue;
    if (line.startsWith("[") && line.endsWith("]")) continue;

    const eq = line.indexOf("=");
    if (eq === -1) continue;

    const key = line.slice(0, eq).trim().toLowerCase();
    const value = stripInlineComment(line.slice(eq + 1));

    if (key === "key_file") {
      keyFileIgnored = true;
      continue;
    }

    const field = KEY_MAP[key];
    if (field && value !== "") {
      fields[field] = value;
      if (!matchedKeys.includes(field)) matchedKeys.push(field);
    }
  }

  return { fields, keyFileIgnored, matchedKeys };
}
