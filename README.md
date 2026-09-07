# SE Onboarding Labs

A series of hands-on labs for Solutions Engineers joining the team. Each lab is
self-contained, runs against a real AWS account, and builds on the one before it.
The focus is Amazon Bedrock — how the models work, how to call them from code, and
how to run that traffic on infrastructure you'd actually ship.

## How these labs work

- **Do them in order.** Later labs assume you've done the earlier ones and reuse
  values you recorded along the way.
- **They're deliberately not click-by-click.** Each lab tells you where to go and
  what to look for; working out the exact clicks is part of the exercise.
  Reflection prompts and hints are hidden behind collapsible reveals — try to
  answer first, then check.
- **You need an AWS account with Bedrock access.** Cisco folks can look up their
  existing accounts at <https://go2.cisco.com/aws>. If you don't have one, email
  **jlunde@cisco.com**.

## Labs

### [Lab 01 — Connecting to AWS & Exploring the Bedrock Playground](lab-01-bedrock-intro/README.md)

Get into an AWS account, find Bedrock, and learn to read a model's Model Catalog
entry for the specs that matter (Model ID, deployment type, inference type,
context window vs. max output tokens). Then run the same prompt against two
models — Amazon Nova Pro and OpenAI GPT-5.6 Luna v1 — side-by-side in the
Playground, and work out why identical questions produce different token counts
and latency. Finishes with the temperature and max-tokens settings.

~45–60 minutes. No prior lab required.

### [Lab 02 — Calling Bedrock Privately from Your Own Windows Box](lab-02-bedrock-private-endpoint/README.md)

Stand up lab infrastructure from a CloudFormation template through the console
(a VPC, a public subnet, and a Windows Server box with the Bruno API client
pre-installed), connect over RDP, and call the Bedrock Runtime API directly —
outside the Playground. Compare two ways to authenticate: an IAM role via
instance metadata vs. a long-term Bedrock API key. Then build an interface VPC
endpoint to force that traffic over AWS PrivateLink instead of the public
internet, prove it's actually taking the private path, and use an IAM condition
key to restrict the credentials to that endpoint.

Requires Lab 01 (you'll reuse the Nova Pro Model ID). The private-endpoint
section is more heavily guided — it's genuinely advanced material.

## Repo layout

```
lab-01-bedrock-intro/          Lab 01 — student-facing README
lab-02-bedrock-private-endpoint/
  README.md                    Lab 02 — student-facing README
  cloudformation/              CloudFormation template + maintainer notes
```
