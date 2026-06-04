import { describe, expect, it } from "vitest";

import { parseOciConfig } from "./parseOciConfig";

const FULL = `[DEFAULT]
user=ocid1.user.oc1..aaaaaaaauser
fingerprint=2a:69:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee
tenancy=ocid1.tenancy.oc1..aaaaaaaatenancy
region=ap-chuncheon-1
key_file=/Users/me/.oci/oci_api_key.pem`;

describe("parseOciConfig", () => {
  it("parses a full Oracle-console config block", () => {
    const { fields, keyFileIgnored, matchedKeys } = parseOciConfig(FULL);
    expect(fields).toEqual({
      user_ocid: "ocid1.user.oc1..aaaaaaaauser",
      fingerprint: "2a:69:11:22:33:44:55:66:77:88:99:aa:bb:cc:dd:ee",
      tenancy_ocid: "ocid1.tenancy.oc1..aaaaaaaatenancy",
      region: "ap-chuncheon-1",
    });
    expect(keyFileIgnored).toBe(true);
    expect(matchedKeys.sort()).toEqual(
      ["fingerprint", "region", "tenancy_ocid", "user_ocid"].sort(),
    );
  });

  it("maps the OCI `tenancy`/`user` keys to *_ocid form fields", () => {
    const { fields } = parseOciConfig(
      "tenancy=ocid1.tenancy.oc1..t\nuser=ocid1.user.oc1..u",
    );
    expect(fields.tenancy_ocid).toBe("ocid1.tenancy.oc1..t");
    expect(fields.user_ocid).toBe("ocid1.user.oc1..u");
  });

  it("handles a partial block (only some keys present)", () => {
    const { fields, keyFileIgnored, matchedKeys } = parseOciConfig(
      "[DEFAULT]\nregion=ap-seoul-1\nuser=ocid1.user.oc1..x",
    );
    expect(fields).toEqual({
      region: "ap-seoul-1",
      user_ocid: "ocid1.user.oc1..x",
    });
    expect(keyFileIgnored).toBe(false);
    expect(matchedKeys.sort()).toEqual(["region", "user_ocid"]);
  });

  it("ignores blank lines, comments, and the section header", () => {
    const input = `; a comment
# another comment

[DEFAULT]
region=ap-tokyo-1
`;
    const { fields } = parseOciConfig(input);
    expect(fields).toEqual({ region: "ap-tokyo-1" });
  });

  it("trims surrounding whitespace and inline comments", () => {
    const { fields } = parseOciConfig(
      "  region = ap-osaka-1   # primary region\n",
    );
    expect(fields.region).toBe("ap-osaka-1");
  });

  it("tolerates CRLF line endings", () => {
    const { fields } = parseOciConfig("region=us-ashburn-1\r\nuser=ocid1.user.oc1..z\r\n");
    expect(fields).toEqual({
      region: "us-ashburn-1",
      user_ocid: "ocid1.user.oc1..z",
    });
  });

  it("reports key_file as ignored without surfacing its value", () => {
    const { fields, keyFileIgnored } = parseOciConfig(
      "key_file=<path>\nregion=eu-frankfurt-1",
    );
    expect("key_file" in fields).toBe(false);
    expect(keyFileIgnored).toBe(true);
  });

  it("returns empty result for garbage / non-ini input", () => {
    const { fields, matchedKeys, keyFileIgnored } = parseOciConfig(
      "this is not a config\njust some prose\n12345",
    );
    expect(fields).toEqual({});
    expect(matchedKeys).toEqual([]);
    expect(keyFileIgnored).toBe(false);
  });

  it("returns empty result for an empty string", () => {
    expect(parseOciConfig("")).toEqual({
      fields: {},
      matchedKeys: [],
      keyFileIgnored: false,
    });
  });

  it("ignores unknown keys", () => {
    const { fields } = parseOciConfig(
      "passphrase=secret\nregion=uk-london-1\nfoo=bar",
    );
    expect(fields).toEqual({ region: "uk-london-1" });
  });
});
