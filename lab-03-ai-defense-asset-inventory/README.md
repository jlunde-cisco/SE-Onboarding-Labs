# Lab 03 — Onboarding an AWS Account into AI Defense

## What you'll learn

By the end of this lab you'll be able to:

- Explain what AI Defense's AI asset discovery does and why you'd connect an AWS account to it
- Connect an AWS account to an AI Defense tenant using the Cloud integration
- Deploy the AI Defense IAM roles into AWS with the supplied CloudFormation stack
- Create an AI resource in AWS (a Bedrock model call, or a Bedrock knowledge base) and find it in AI Defense's **AI Inventory**
- Describe, at a high level, how discovery stays current (the daily scan vs. the optional CloudTrail integration)

This one is shorter and lighter than the earlier labs — it's an overview, not a deep dive. **Watch the onboarding video first** (link below); this README is the map to follow along and the place to record what you saw.

> **Watch this first:** Jason's AI Defense AWS onboarding walkthrough —
> <https://app.vidcast.io/share/28ab03e3-7d1e-4425-a3d9-891b7a36dba3>
>
> Primary Cisco docs for this lab:
> - AWS Integration for AI Asset Discovery — <https://securitydocs.cisco.com/docs/ai-def/user/169320.dita>
> - Enable CloudTrail Integration — <https://securitydocs.cisco.com/docs/ai-def/user/169321.dita>

As with the other labs: this tells you where to go and what to look for, not every click. Reflection prompts are hidden behind collapsible reveals — try to answer first, then check.

---

## Prerequisites

- **An AWS account you have administrator access to.** You should already have one from Lab 01. Every AI Defense SE is expected to have an AWS account — if you don't, **email jlunde@cisco.com** and he'll get you sorted.
  - You need enough access to **deploy a CloudFormation stack that creates IAM roles** in that account. For this lab, use **Account** scope against your own single account — not Organization scope.
- **Access to an AI Defense tenant with the Administrator role.** Creating and editing integrations requires it; the Analyst role can only view them. How the team hands out AI Defense tenant access is coordinated by **jlunde@cisco.com** — check with him before you start so you're working in the right tenant.
- The AWS integration is currently a **beta / limited-release** feature in AI Defense. If you don't see the **Cloud** tab under Integrations, that's why — again, check with Jason.
- A modern browser and about 30–45 minutes. Have both the AWS console and the AI Defense console open — you'll bounce between them.

---

## Part 1 — What Asset Discovery Is For

Before clicking anything, get the concept straight.

AI Defense keeps an **AI Inventory** — a running list of the AI/ML resources in your environment: the Bedrock foundation models being invoked, Bedrock agents and knowledge bases, SageMaker endpoints, and so on. You can't govern (validate, apply policy to, watch for drift on) an AI asset you don't know exists, so inventory is step one.

To build that inventory for AWS, AI Defense needs read access **into your AWS account**. You grant it by deploying a small CloudFormation stack that creates one or two IAM roles AI Defense can assume:

- a **discovery role** (`CiscoAIDefenseAssetInventoryRole`) — read-only, used to enumerate AI/ML resources
- an **action role** (`CiscoAIDefenseAssetActionRole`) — used later for AI Validation and other actions on discovered assets (optional capability; "perform actions on assets")

Nothing about your models or data leaves your account beyond the resource metadata AI Defense needs to list the asset — type, ARN, region, timestamps.

<details>
<summary><strong>How is this different from the auth you did in Lab 02?</strong></summary>

In Lab 02 *you* held credentials (an IMDS-sourced role, or a Bedrock API key) and called AWS. Here it's inverted: a **third-party SaaS (AI Defense) assumes a role in your account**. That's the classic cross-account `sts:AssumeRole` pattern — you create a role, its trust policy names AI Defense's AWS principal (and usually an external ID to prevent confused-deputy attacks), and AI Defense assumes it on a schedule. You're not handing out a long-lived key; you're delegating a scoped, revocable role. Delete the CloudFormation stack and the access is gone.

</details>

---

## Part 2 — Add the AWS Integration in AI Defense

In the **AI Defense** console:

1. Go to **Administration → Integrations**, and open the **Cloud** tab.
2. Click **Add integration**.
3. Fill in the **Connection Configuration**:
   - **Display name** — something you'll recognize, e.g. `<your-name>-lab3-aws`.
   - **Scope** — choose **Account** for this lab. (Organization scope onboards every account under an AWS Org OU at once via a StackSet — powerful, but not what you want against your personal lab account.)
   - **Account ID** — your 12-digit AWS account ID.
   - **Capabilities** — beyond the default asset discovery, you can enable:
     - **Perform actions on assets** — adds the action role, needed later for AI Validation. Safe to enable now.
     - **Read CloudTrail Events** — near-real-time detection instead of waiting for the daily scan. Leave this **off** for the lab unless you want the bonus in Part 6 — it needs extra CloudFormation and an existing CloudTrail S3 bucket.
4. Continue to the **Deploy roles** screen. Keep this browser tab open — you'll come back to it.

---

## Part 3 — Deploy the IAM Roles in AWS

Still on the **Deploy roles** screen in AI Defense:

1. Make sure your browser is logged into the **correct AWS account** (the one whose ID you just entered).
2. Click **Launch CloudFormation in AWS**. This opens the AWS CloudFormation console with a **Quick create stack** form, most fields pre-filled from AI Defense (the AI Defense principal, external ID, and role names are baked into the template parameters).
3. Review the parameters. Scroll to the bottom and **acknowledge the IAM capabilities checkbox** (the stack creates named IAM roles).
4. Click **Create stack** and wait for **CREATE_COMPLETE**.
5. Open the stack's **Outputs** tab and copy the role ARNs:

   | Scope | Outputs to copy |
   |---|---|
   | Account | **Discovery role ARN**, **Action role ARN** |

<details>
<summary><strong>What did that stack actually create?</strong></summary>

For Account scope: the two IAM roles (`CiscoAIDefenseAssetInventoryRole`, `CiscoAIDefenseAssetActionRole`) and their policies. The discovery role's policy is read-only across the AI/ML services AI Defense inventories (Bedrock, SageMaker, etc.). Each role's **trust policy** allows AI Defense's AWS account to assume it, conditioned on an **external ID** that's unique to your connector. No compute, no data resources — just IAM.

</details>

---

## Part 4 — Complete the Connection

Back on the AI Defense **Deploy roles** screen:

1. Paste in the **Discovery role ARN** and **Action role ARN** from the stack outputs.
2. (Only if you enabled Read CloudTrail Events — see Part 6 — also paste the **SQS Queue URL** from that stack.)
3. Click **Complete**.

AI Defense now validates the connection: it assumes the discovery role, and confirms the permissions resolve. When it succeeds, the integration shows **Active** in the **Administration → Integrations → Cloud** table.

If it shows **Failed**, the usual cause is the wrong AWS account (roles deployed somewhere other than the account ID you entered) or the stack not finishing. Re-check and re-enter the ARNs.

---

## Part 5 — Create an AI Asset in AWS

You've connected the account, but a fresh lab account probably has no AI/ML resources for AI Defense to find. Make one. Either option works — pick one (or do both):

### Option A — Invoke a Bedrock model (fastest)

Open **AWS CloudShell** (the `>_` icon in the AWS console top bar — it's pre-authenticated as you, nothing to install) and call a model with the AWS CLI. Reuse the Lab 01 prompt:

```bash
aws bedrock-runtime converse \
  --region us-east-1 \
  --model-id us.amazon.nova-pro-v1:0 \
  --messages '[{"role":"user","content":[{"text":"How much wood could a woodchuck chuck if a woodchuck could chuck wood?"}]}]'
```

Note the `us.` prefix on the model ID — that's the **cross-region inference profile** for Nova Pro, the same gotcha you hit in Lab 02 (Nova Pro can't be invoked on-demand by its bare model ID). Swap the region if your Bedrock access is elsewhere.

A model that's been *invoked* shows up in the inventory as a foundation model in use — this is exactly what the daily scan looks for.

### Option B — Create a Bedrock knowledge base (a discrete resource)

In the Bedrock console, go to **Knowledge Bases → Create**. Use the **quick-create** path for the vector store so you don't have to stand up OpenSearch yourself; point it at a tiny S3 bucket with one text file. This gives you a named, first-class resource (with its own ARN) rather than "a model that got called once" — closer to the kind of asset you'll usually be governing.

Whichever you pick, **note the region and the resource name/ID** — you'll look for it next.

---

## Part 6 — Find It in the AI Inventory

In AI Defense, go to the **AI Assets** navigation tab and open **AI Inventory**.

- Filter or search for the AWS account you connected. You should see your asset — the Nova Pro model, or the knowledge base — attributed to that account and region.
- Click into it. Note what AI Defense records: resource type, ARN, region, account, first-seen / last-seen timestamps, and (for models) usage signal.

**Timing matters here.** Scheduled discovery runs **about once a day**, so a resource you just created may not appear immediately. Options:

- Trigger a re-scan from the integration if your tenant exposes that control, or
- Just wait for the next daily scan and check back, or
- Set up the **CloudTrail integration** (below) for ~10-minute detection.

<details>
<summary><strong>Bonus — near-real-time detection with CloudTrail</strong></summary>

The daily scan is fine for inventory but slow for "someone just spun up a Bedrock agent." The **CloudTrail integration** closes that gap:

1. In the connector, enable **Read CloudTrail Events**.
2. Deploy a second CloudFormation stack (`ai-defense-aws-cloudtrail.yaml`) in the account that holds your **CloudTrail S3 bucket** — it creates an SNS topic + SQS queue.
3. Add an **S3 event notification** on the CloudTrail bucket (prefix `AWSLogs/`, suffix `.json.gz`) targeting that SNS topic.
4. Paste the **SQS Queue URL** back into the AI Defense connector and re-complete.

AI Defense then polls the queue every ~60s and re-discovers just the affected resource type, so changes land in the inventory within ~10 minutes. All the log infrastructure and raw logs stay in your account. Full steps: <https://securitydocs.cisco.com/docs/ai-def/user/169321.dita>

This needs an existing CloudTrail trail delivering to S3 — if your lab account doesn't have one, that's a prerequisite to sort first.

</details>

---

## Cleanup

Leaving this connected is fine if you'll keep using the tenant — but if it's throwaway:

1. In AI Defense, **delete the integration** (Administration → Integrations → Cloud → delete). This stops discovery for the account.
2. In AWS CloudFormation, **delete the IAM roles stack** (and the CloudTrail stack if you did the bonus).
3. If you did Option B, **delete the Bedrock knowledge base** and its S3 bucket / vector store so they don't sit around.
4. Option A leaves nothing running — a past model invocation costs nothing going forward.

---

## Wrap-Up

Before you're done, make sure you can answer these in your own words:

1. What is the **AI Inventory**, and why is discovery the first step in governing AI assets?
2. In this lab, who assumes a role in whose account — and how is that the reverse of the auth you set up in Lab 02?
3. What does the CloudFormation stack create, and what's the one checkbox you have to acknowledge before it will deploy?
4. Your new resource didn't show up in the inventory right away. Why not, and what are your options to make discovery faster?
5. What's the difference between the **discovery role** and the **action role**, and when does the action role start to matter?

Drop questions in the team channel — and if the video and this README disagree on any UI detail, trust the video (or the Cisco docs) and flag it to Jason so this can be fixed.
