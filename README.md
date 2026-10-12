
# FMC SNMPv3 Password Updater

A Python script that reads the **SNMP configuration** from **Cisco Secure Firewall Management Center (FMC)** FTD Platform Settings policies and can **change the authentication password of an SNMPv3 user** through the FMC REST API.

---

## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Arguments](#arguments)
- [Examples](#examples)
- [Example Run](#example-run)
- [Error Handling](#error-handling)
- [Important Notes](#important-notes)
- [Troubleshooting](#troubleshooting)
- [Disclaimer](#disclaimer)

---

## Features

- Authenticates to FMC and retrieves the API token and Domain UUID automatically
- Lists all FTD Platform Settings policies, with pagination support
- **Read mode:** exports the SNMP settings of one or all policies as JSON
- **Update mode:** changes the `authenticationPassword` of a given SNMPv3 user with an HTTP `PUT`
- Exits with a clear error message if the SNMPv3 user is **not found**
- Prompts securely for passwords if they are not given as arguments
- Supports HTTPS proxies via the `HTTPS_PROXY` / `https_proxy` environment variables
- Has an optional `--insecure` flag for FMCs with self-signed certificates

---

## Requirements

| Component      | Version / Details                                              |
|----------------|----------------------------------------------------------------|
| Python         | 3.8 or later                                                   |
| Python package | `requests`                                                     |
| Cisco FMC      | 7.x or later (the `snmpsettings` endpoint must be available)   |
| FMC user       | API-enabled account with permission to modify Platform Settings |

API endpoint used:

```
GET/PUT /api/fmc_config/v1/domain/{domainUUID}/policy/ftdplatformsettingspolicies/{containerUUID}/snmpsettings[/{objectId}]
```

---

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/Gyuri1/FMC_SNMP_Platform_Settings.git
cd fmc-snmpv3
```

### 2. (Recommended) Create a virtual environment

**Linux / macOS**

```bash
python3 -m venv venv
source venv/bin/activate
```

**Windows (PowerShell)**

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install requests
```

Or, using the requirements file:

```bash
pip install -r requirements.txt
```

`requirements.txt`:

```
requests>=2.25.0
```

---

## Configuration

You can pass connection details as command-line arguments or set them as environment variables.

| Environment Variable          | Description                            |
|-------------------------------|----------------------------------------|
| `FMC_HOST`                    | FMC hostname or IP address             |
| `FMC_USER`                    | FMC API username                       |
| `FMC_PASSWORD`                | FMC API password                       |
| `HTTPS_PROXY` / `https_proxy` | Proxy URL (optional)                   |

**Linux / macOS**

```bash
export FMC_HOST=fmc.company.com
export FMC_USER=admin
export HTTPS_PROXY=http://proxy.company.com:8080   # optional
```

**Windows (PowerShell)**

```powershell
$env:FMC_HOST = "fmc.company.com"
$env:FMC_USER = "admin"
$env:HTTPS_PROXY = "http://proxy.company.com:8080"   # optional
```

---

## Usage

```bash
python fmc-snmpv3.py --host <FMC> --user <USER> [--policy <POLICY>] [--SNMPUser <USER> --SNMPPassword <PASS>] [options]
```

The script runs in one of two modes:

| Mode        | Triggered by          | Action                                                  |
|-------------|-----------------------|---------------------------------------------------------|
| **Read**    | *(default)*           | Prints or saves the SNMP settings as JSON               |
| **Update**  | `--SNMPUser` is given | Changes the SNMPv3 user's authentication password (PUT) |

---

## Arguments

| Argument         | Required | Description                                                         |
|------------------|----------|---------------------------------------------------------------------|
| `--host`         | Yes*     | FMC hostname or IP (or set `FMC_HOST`)                              |
| `--user`         | Yes*     | FMC API username (or set `FMC_USER`)                                |
| `--password`     | No       | FMC password (or set `FMC_PASSWORD`; prompted if omitted)           |
| `--policy`       | No       | Platform Settings policy name (default: **all policies**)           |
| `--domain`       | No       | Override the Domain UUID (default: taken from the auth token)       |
| `--insecure`     | No       | Disable TLS certificate verification                                |
| `--output`       | No       | Save the read-mode result to a JSON file                            |
| `--SNMPUser`     | No       | SNMPv3 user whose password is changed (enables update mode)         |
| `--SNMPPassword` | No       | New SNMPv3 authentication password (prompted if omitted)            |

\* Required unless the matching environment variable is set.

---

## Examples

### Read the SNMP settings of all policies

```bash
python fmc-snmpv3.py --host fmc.company.com --user admin --insecure
```

### Read one policy and save it to a file

```bash
python fmc-snmpv3.py --host fmc.company.com --user admin --policy "FTD1" --output snmp.json
```

### Change an SNMPv3 user password

```bash
python fmc-snmpv3.py --host fmc.company.com --user admin --insecure \
    --policy "FTD1" --SNMPUser cisco --SNMPPassword 'NewS3cretPass!'
```

### Change the password with a secure prompt (keeps it out of shell history)

```bash
python fmc-snmpv3.py --host fmc.company.com --user admin --policy "FTD1" --SNMPUser cisco
```

---

## Example Run

```
python fmc-snmpv3.py --host fmc.company.com --user admin --insecure --policy "FTD1" --SNMPUser cisco --SNMPPassword 'NewS3cretPass!'
FMC password: 
[+] Reading SNMP settings: FTD1 (005056AE-FC0E-0ed3-0000-008589934901)
    [OK] Password updated for SNMPv3 user 'cisco'.
[+] Done. Deploy the policy to apply the change on the FTD devices.
```

### Example read-mode output (JSON)

```json
[
  {
    "policyName": "FTD1",
    "policyId": "005056AE-FC0E-0ed3-0000-008589934901",
    "snmpSettings": [
      {
        "snmpv3Users": [
          {
            "securityLevel": "Auth",
            "userName": "cisco",
            "authAlgoType": "SHA224",
            "authenticationPassword": "***********",
            "encryptionPasswordType": "Clear"
          }
        ]
      }
    ]
  }
]
```

---

## Error Handling

### SNMPv3 user not found

```
python fmc-snmpv3.py --host fmc.company.com --user admin --insecure --policy "FTD1" --SNMPUser unknown
FMC password: 
New SNMPv3 password for 'unknown': 
[+] Reading SNMP settings: FTD1 (005056AE-FC0E-0ed3-0000-008589934901)
    - SNMPv3 user 'unknown' not found in this policy.
ERROR: SNMPv3 user 'unknown' was NOT found among the SNMPv3 users of the selected policy/policies.
```

### Exit codes

| Code | Meaning                                                                        |
|------|--------------------------------------------------------------------------------|
| `0`  | Success                                                                        |
| `1`  | Error: authentication, policy not found, user not found, PUT failed, connection |
| `2`  | Invalid or missing command-line arguments                                      |

---

## Important Notes

- **Deployment required:** Changes are saved on FMC only. You must **deploy** the policy to apply them to the FTD devices.
- **Use `--policy`:** Without it, the password is changed in **every** policy that contains the SNMPv3 user.
- **Masked passwords:** FMC returns the other users' passwords masked (`***********`). The script sends them back unchanged, and FMC normally keeps the existing values. **Test in a lab first.**
- **Priv security level:** Only `authenticationPassword` is changed. The `encryptionPassword` of `Priv` users is not modified.
- **Dedicated API user:** Generating a token logs out other sessions of the same FMC user. Use a dedicated API account.
- **Token lifetime:** FMC tokens are valid for 30 minutes.

---

## Troubleshooting

| Problem                                    | Possible Cause / Solution                                                  |
|--------------------------------------------|----------------------------------------------------------------------------|
| `SSL: CERTIFICATE_VERIFY_FAILED`           | The FMC uses a self-signed certificate. Use `--insecure` or install the CA. |
| `401 Unauthorized`                         | Wrong credentials, or the user is not API-enabled.                         |
| `403 Forbidden`                            | The user role lacks permission to modify Platform Settings.               |
| `404 Not Found` on `snmpsettings`          | The FMC version does not support the endpoint. Check the API Explorer.     |
| `Policy 'X' not found`                     | Check the exact (case-sensitive) policy name in FMC.                       |
| Connection timeout                         | Check network access, firewall rules, or the `HTTPS_PROXY` setting.        |

You can explore the API in FMC's built-in **API Explorer**:

```
https://<fmc>/api/api-explorer
```

---

## Example:

```python fmc-snmpv3.py --host fmc.company.com --user admin --insecure --policy "FTD1" --SNMPUser cisco --SNMPPassword 'NewS3cretPass!'
FMC password: 
[+] Reading SNMP settings: FTD1 (005056AE-FC0E-0ed3-0000-008589933901)
    [OK] Password updated for SNMPv3 user 'cisco'.
[+] Done. Deploy the policy to apply the change on the FTD devices.
```


## Disclaimer

This script is provided **as-is**, without warranty of any kind. Test it in a lab environment before using it in production. It is not an official Cisco tool.



