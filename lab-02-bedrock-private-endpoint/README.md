# Lab 02 — Reaching Bedrock Runtime Through a Private Endpoint

> **Status: scaffolding.** This is the infrastructure (CloudFormation) for
> the lab. The step-by-step student-facing instructions (in the style of
> [Lab 01](../lab-01-bedrock-intro/README.md)) will be written once the
> template is finalized.

## What this stack builds

- A new VPC (CIDR and name are parameters — each engineer names their own)
- One public subnet with an Internet Gateway + route so the box has a real public IP
- A security group allowing **RDP (3389) only from the deploying engineer's own IP**
- A Windows Server 2016 EC2 instance (latest AMI, resolved automatically via the public SSM parameter)
- An **interface VPC endpoint (PrivateLink)** for `bedrock-runtime`, with private DNS enabled, and a security group that only allows the lab instance to reach it
- An IAM role attached to the instance, scoped to `bedrock:InvokeModel` / `InvokeModelWithResponseStream` on **Amazon Nova Lite only**

The intent: the instance has internet access via the IGW, but because the
interface endpoint has private DNS enabled, calls to the standard
`bedrock-runtime.<region>.amazonaws.com` hostname resolve to the private
endpoint inside the VPC instead of leaving over the internet. Students
verify this from the Windows box using Postman or Bruno.

## Template

[`cloudformation/windows-bedrock-lab.yaml`](cloudformation/windows-bedrock-lab.yaml)

Validated with `aws cloudformation validate-template` — clean syntax, no
inherent template errors. `describe-vpc-endpoint-services` confirmed
`com.amazonaws.us-east-1.bedrock-runtime` exists as an Interface endpoint
service, so this is known to work in `us-east-1`. If you deploy in a
different region, the service should still exist for Bedrock Runtime, but
worth a quick re-check.

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
| `NovaLiteModelId` | `amazon.nova-lite-v1:0` | Used to scope the IAM policy resource ARN |

### Deploy

```bash
aws cloudformation deploy \
  --template-file cloudformation/windows-bedrock-lab.yaml \
  --stack-name my-bedrock-lab \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    VpcName=jsmith-bedrock-lab \
    MyIP=203.0.113.5/32 \
    KeyPairName=my-keypair
```

`CAPABILITY_NAMED_IAM` is required because the stack creates an IAM role
and instance profile with an explicit name.

### Outputs

- `InstancePublicIp` — RDP here
- `BedrockRuntimeEndpointId`
- `IamRoleName` — the role attached to the instance (Nova Lite only)

## Open items / things I expect to adjust

- Decide whether the instance keeps a public IP + IGW route at all once
  private-endpoint access is proven, or whether a follow-on variant should
  move it to a fully private subrouting with a bastion/SSM-only access
  path (role already has `AmazonSSMManagedInstanceCore` attached, so
  Session Manager works as an RDP alternative or fallback today).
- Whether to bake AWS CLI + Postman/Bruno installation into `UserData`
  versus having the student install them manually as part of the lab.
- Final student-facing lab instructions (mirroring the Lab 01 style —
  high-level, exploratory, no exact click paths) once the above is settled.
