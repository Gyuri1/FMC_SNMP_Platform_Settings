#!/usr/bin/env python3
"""
Read SNMP settings from Cisco FMC FTD Platform Settings policies and
optionally change the authentication password of an SNMPv3 user.

API used:
  GET/PUT /api/fmc_config/v1/domain/{domainUUID}/policy/ftdplatformsettingspolicies/{containerUUID}/snmpsettings[/{objectId}]

Proxy: honors HTTPS_PROXY / https_proxy environment variables automatically.
"""

import argparse
import copy
import getpass
import json
import os
import sys

import requests
import urllib3

PLATFORM_AUTH = "/api/fmc_platform/v1/auth/generatetoken"
POLICIES_PATH = "/api/fmc_config/v1/domain/{domain}/policy/ftdplatformsettingspolicies"
SNMP_PATH = POLICIES_PATH + "/{container}/snmpsettings"
PAGE_LIMIT = 1000
READ_ONLY_FIELDS = ("links", "metadata")


class FMCClient:
    def __init__(self, host, username, password, verify=True, timeout=30):
        self.base = f"https://{host}"
        self.verify = verify
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = True  # use HTTPS_PROXY / https_proxy
        self.session.headers.update({"Accept": "application/json"})
        self.domain_uuid = None
        self._auth(username, password)

    def _auth(self, username, password):
        r = self.session.post(
            self.base + PLATFORM_AUTH,
            auth=(username, password),
            verify=self.verify,
            timeout=self.timeout,
        )
        r.raise_for_status()
        token = r.headers.get("X-auth-access-token")
        self.domain_uuid = r.headers.get("DOMAIN_UUID")
        if not token or not self.domain_uuid:
            sys.exit("ERROR: Authentication failed - token or DOMAIN_UUID missing.")
        self.session.headers.update({"X-auth-access-token": token})

    def get(self, path, params=None):
        r = self.session.get(
            self.base + path, params=params, verify=self.verify, timeout=self.timeout
        )
        r.raise_for_status()
        return r.json()

    def put(self, path, payload):
        r = self.session.put(
            self.base + path, json=payload, verify=self.verify, timeout=self.timeout
        )
        if not r.ok:
            raise requests.HTTPError(f"{r.status_code} {r.reason}: {r.text}", response=r)
        return r.json()

    def get_all(self, path, params=None):
        """Retrieve all items with pagination."""
        params = dict(params or {}, limit=PAGE_LIMIT, offset=0)
        items = []
        while True:
            data = self.get(path, params)
            items.extend(data.get("items", []))
            if not data.get("paging", {}).get("next"):
                break
            params["offset"] += PAGE_LIMIT
        return items

    def get_platform_policies(self):
        return self.get_all(POLICIES_PATH.format(domain=self.domain_uuid))

    def get_snmp_settings(self, container_uuid):
        path = SNMP_PATH.format(domain=self.domain_uuid, container=container_uuid)
        data = self.get(path, params={"expanded": "true"})
        # Some FMC versions return a list of items; fetch full details per ID.
        if "items" in data:
            return [self.get(f"{path}/{item['id']}") for item in data["items"]]
        return [data]

    def update_snmp_settings(self, container_uuid, settings):
        path = SNMP_PATH.format(domain=self.domain_uuid, container=container_uuid)
        payload = {k: v for k, v in settings.items() if k not in READ_ONLY_FIELDS}
        return self.put(f"{path}/{settings['id']}", payload)


def set_snmpv3_password(settings, snmp_user, snmp_password):
    """Return modified copy of settings, or None if the user is not present."""
    new_settings = copy.deepcopy(settings)
    for user in new_settings.get("snmpv3Users", []):
        if user.get("userName") == snmp_user:
            user["authenticationPassword"] = snmp_password
            return new_settings
    return None


def main():
    p = argparse.ArgumentParser(description="Read/update SNMP settings in FMC Platform Settings")
    p.add_argument("--host", default=os.getenv("FMC_HOST"), help="FMC hostname/IP")
    p.add_argument("--user", default=os.getenv("FMC_USER"), help="FMC username")
    p.add_argument("--password", default=os.getenv("FMC_PASSWORD"), help="FMC password")
    p.add_argument("--policy", help="Platform Settings policy name (default: all)")
    p.add_argument("--domain", help="Override domain UUID (default: from token)")
    p.add_argument("--insecure", action="store_true", help="Disable TLS verification")
    p.add_argument("--output", help="Save result to a JSON file")
    p.add_argument("--SNMPUser", dest="snmp_user", help="SNMPv3 user whose password is changed")
    p.add_argument("--SNMPPassword", dest="snmp_password",
                   help="New SNMPv3 authentication password (prompted if omitted)")
    args = p.parse_args()

    if not args.host or not args.user:
        p.error("--host and --user are required (or set FMC_HOST / FMC_USER)")
    if args.snmp_password and not args.snmp_user:
        p.error("--SNMPPassword requires --SNMPUser")

    password = args.password or getpass.getpass("FMC password: ")
    snmp_password = None
    if args.snmp_user:
        snmp_password = args.snmp_password or getpass.getpass(
            f"New SNMPv3 password for '{args.snmp_user}': ")
        if not snmp_password:
            sys.exit("ERROR: SNMPv3 password must not be empty.")

    if args.insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        fmc = FMCClient(args.host, args.user, password, verify=not args.insecure)
        if args.domain:
            fmc.domain_uuid = args.domain

        policies = fmc.get_platform_policies()
        if args.policy:
            policies = [pol for pol in policies if pol.get("name") == args.policy]
            if not policies:
                sys.exit(f"ERROR: Policy '{args.policy}' not found.")

        result = []
        user_found = False
        update_failed = False

        for pol in policies:
            print(f"[+] Reading SNMP settings: {pol['name']} ({pol['id']})", file=sys.stderr)
            try:
                snmp_list = fmc.get_snmp_settings(pol["id"])
            except requests.HTTPError as e:
                print(f"    ! Failed: {e}", file=sys.stderr)
                result.append({"policyName": pol["name"], "policyId": pol["id"], "snmpSettings": None})
                continue

            # --- Update mode ---
            if args.snmp_user:
                for settings in snmp_list:
                    modified = set_snmpv3_password(settings, args.snmp_user, snmp_password)
                    if modified is None:
                        print(f"    - SNMPv3 user '{args.snmp_user}' not found in this policy.",
                              file=sys.stderr)
                        continue
                    user_found = True
                    try:
                        fmc.update_snmp_settings(pol["id"], modified)
                        print(f"    [OK] Password updated for SNMPv3 user '{args.snmp_user}'.",
                              file=sys.stderr)
                    except requests.HTTPError as e:
                        update_failed = True
                        print(f"    ! PUT failed: {e}", file=sys.stderr)
                continue

            # --- Read mode ---
            result.append({"policyName": pol["name"], "policyId": pol["id"], "snmpSettings": snmp_list})

        if args.snmp_user:
            if not user_found:
                sys.exit(f"ERROR: SNMPv3 user '{args.snmp_user}' was NOT found "
                         f"among the SNMPv3 users of the selected policy/policies.")
            if update_failed:
                sys.exit("ERROR: One or more updates failed.")
            print("[+] Done. Deploy the policy to apply the change on the FTD devices.",
                  file=sys.stderr)
            return

        output = json.dumps(result, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"[+] Saved to {args.output}", file=sys.stderr)
        else:
            print(output)

    except requests.HTTPError as e:
        sys.exit(f"HTTP error: {e}")
    except requests.RequestException as e:
        sys.exit(f"Connection error: {e}")


if __name__ == "__main__":
    main()