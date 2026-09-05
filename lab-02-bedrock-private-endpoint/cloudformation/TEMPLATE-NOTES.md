# Lab 02 Template Notes

> **This is a build/maintainer reference, not the lab.** Student-facing
> instructions live at [../README.md](../README.md). This file documents
> the CloudFormation template itself — parameters, deploy mechanics, and
> a changelog of bugs hit and fixed while building it — for whoever
> maintains this lab later.

## What this stack builds

- A new VPC (CIDR and name are parameters — each engineer names their own)
- One public subnet with an Internet Gateway + route so the box has a real public IP
- A security group allowing **RDP (3389) only from the deploying engineer's own IP**
- A Windows Server 2016 EC2 instance (latest AMI, resolved automatically via the public SSM parameter), with **Bruno silently installed via UserData** at first boot so it's ready when the engineer RDPs in

Beyond that it's deliberately minimal. The **Bedrock Runtime PrivateLink
interface endpoint** (with its own security group) and any **IAM
role/policy or IAM user access keys** are *not* provisioned by this
template — students build and compare both authentication paths by hand,
and build the interface VPC endpoint for `bedrock-runtime` (with private
DNS enabled) themselves, then verify that calls to the standard
`bedrock-runtime.<region>.amazonaws.com` hostname actually resolve to the
private endpoint instead of leaving over the internet. See
[../README.md](../README.md) for the full walkthrough — this stack only
covers what's needed to get the engineer an RDP-reachable Windows box
with Bruno preinstalled.

## Template

[`windows-bedrock-lab.yaml`](windows-bedrock-lab.yaml)

Validated with `aws cloudformation validate-template` — clean syntax, no
inherent template errors. `describe-vpc-endpoint-services` confirmed
`com.amazonaws.us-east-1.bedrock-runtime` exists as an Interface endpoint
service, so this is known to work in `us-east-1`. If you deploy in a
different region, the service should still exist for Bedrock Runtime, but
worth a quick re-check.

### Fixed since last review

- The RDP security group's `GroupDescription` originally read *"...the
  deploying engineer's IP only"* — the apostrophe isn't in EC2's allowed
  character set for security group descriptions
  (`a-zA-Z0-9. _-:/()#,@[]+=&;{}!$*`), which is exactly the
  `InvalidRequest` error you hit. Reworded to avoid the possessive
  entirely: *"Allow RDP from the IP of the deploying engineer"*. Re-ran
  `validate-template` against both the YAML and JSON afterward — clean.
- The Bruno install failed at first boot with `Could not create SSL/TLS
  secure channel` — Windows Server 2016's .NET Framework defaults to
  SSL3/TLS1.0 for outbound HTTPS in PowerShell, and GitHub (like most
  modern hosts) rejects that handshake. Added
  `[Net.ServicePointManager]::SecurityProtocol = ... -bor
  [Net.SecurityProtocolType]::Tls12` at the top of the UserData script,
  before the `Invoke-WebRequest` call. Re-validated the template
  afterward.

### Parameters

| Parameter | Default | Notes |
|---|---|---|
| `VpcName` | *(required)* | Name tag for the VPC — each engineer picks their own |
| `VpcCidr` | `10.0.0.0/16` | Any private range works |
| `PublicSubnetCidr` | `10.0.1.0/24` | Must fall inside `VpcCidr` |
| `MyIP` | *(required)* | Your public IP in CIDR form, e.g. `203.0.113.5/32` — locks down RDP |
| `KeyPairName` | *(required)* | Must be an existing EC2 key pair in the target region |
| `InstanceType` | `t3.medium` | `t3.large`/`t3.xlarge`/`m5.large`/`m5.xlarge` also allowed |
| `RootVolumeSizeGiB` | `50` | 30–200 |
| `LatestWindowsAmiId` | SSM alias for Windows Server 2016 | Auto-resolves, don't need to hardcode an AMI ID |
| `BrunoVersion` | `4.1.0` | Pinned version silently installed via UserData; bump when a newer Bruno release comes out |

### Before you deploy: create a key pair

The `KeyPairName` parameter requires an **existing** EC2 key pair — the
stack does not create one for you, and this needs to happen first or
there's nothing to select in the console dropdown. Each engineer should
create their own:

1. In the AWS Console, go to **EC2 → Network & Security → Key Pairs → Create key pair**.
2. Give it a name you'll recognize (e.g. `<yourname>-bedrock-lab`).
3. Key pair type: **RSA**. Private key format: **.pem** (or **.ppk** if using PuTTY).
4. Click **Create key pair** — the private key file downloads automatically and **only** at this moment; AWS does not store a copy. Save it somewhere safe. You'll need it after the instance launches to decrypt the Windows Administrator password (EC2 console → select the instance → **Get Windows password**).

### Deploy (AWS Console)

This stack is meant to be deployed through the CloudFormation console, not
the CLI:

1. Go to **CloudFormation → Stacks → Create stack → With new resources (standard)**.
2. Under **Prerequisite - Prepare template**, choose **Template is ready**.
3. Under **Specify template**, choose **Amazon S3 URL** and paste in:

   ```
   https://raw.githubusercontent.com/jlunde-cisco/SE-Onboarding-Labs/main/lab-02-bedrock-private-endpoint/cloudformation/windows-bedrock-lab.yaml
   ```

   (Despite the field's name, CloudFormation accepts any public HTTPS URL
   that serves the template — YAML or JSON, doesn't matter — not only
   actual S3 URLs. This raw GitHub link works. It'll only resolve once
   this file is pushed to the repo.)
4. **Next** — fill in the parameters (`VpcName`, `MyIP`, `KeyPairName` from
   the step above, and anything else you want to change from its default).
5. **Next** through the stack options screen (nothing needs changing —
   this template has no IAM resources, so there's no capability
   acknowledgment checkbox to worry about).
6. Review and **Submit**. Watch the **Events** tab; it typically takes
   several minutes for the Windows instance to reach `CREATE_COMPLETE`.
7. Once complete, check the **Outputs** tab for `InstancePublicIp` to RDP to.

### Outputs

- `InstancePublicIp` — RDP here
- `VpcId`, `PublicSubnetId`, `InstanceId` — handy when building the VPC
  endpoint and IAM role by hand afterward

### Confirming the Bruno install after RDP'ing in

UserData installs Bruno once at first boot, silently (no visible progress
in the RDP session while it runs — expect it to take roughly a minute).
Check for one of these on the `C:\` drive:

- `C:\lab-bootstrap-complete.txt` — install succeeded
- `C:\lab-bootstrap-failed.txt` — install failed; check `C:\lab-bootstrap.log`
  and `%TEMP%\bruno-msi.log` for details (common cause: outbound HTTPS to
  GitHub being blocked)

## Open items / things I expect to adjust

- Bruno's MSI asset naming/version is confirmed as of `4.1.0`
  (`bruno_<version>_x64_win.msi` on the GitHub releases page) — worth a
  spot-check if this sits unused for a while before the next cohort, in
  case the project changes its release asset naming.
