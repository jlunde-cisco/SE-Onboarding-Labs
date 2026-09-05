# Lab 02 — Calling Bedrock Privately from Your Own Windows Box

## What you'll learn

By the end of this lab you'll be able to:

- Stand up lab infrastructure from a CloudFormation template through the AWS console
- Connect to a Windows EC2 instance over RDP
- Call the Bedrock Runtime API directly — outside the console Playground — using Bruno
- Explain the difference between authenticating with an IAM role attached to an instance vs. a long-term Bedrock API key
- Force that API traffic over AWS PrivateLink instead of the public internet, and prove it's actually happening
- Explain the difference between a network path that happens to be private and credentials that are actually, enforceably restricted to that path — and how to build the latter with an IAM condition key

As with Lab 01: don't rush to exact click paths. This lab hands you the pieces and tells you what to look for — working out precisely where to click is part of the exercise. A few steps (the private endpoint section especially) are more heavily guided, since that's genuinely advanced material.

---

## Prerequisites

- **Lab 01 completed.** You'll reuse the Nova Pro **Model ID** you documented there — go dig it back up if you don't have it handy.
- An AWS account with Bedrock access (see Lab 01's prerequisites if you still need one — `jlunde@cisco.com` / `go2.cisco.com/aws`).
- Your AWS account here is likely **shared with other engineers going through this same lab.** That matters for naming — see the callout in Part 2.

---

## Part 1 — Connect to AWS

Sign in the same way you did in Lab 01. Note which **region** you're working in — you'll need it a few times later (it shows up in API URLs). If you're not sure Nova Pro is available in your current region, check back against what you found in Lab 01's model catalog.

---

## Part 2 — Create a Key Pair

Before you can deploy anything, you need an EC2 key pair. The lab's CloudFormation template does **not** create one for you — it expects an existing key pair to already exist in your account/region, or you won't have anything to select when you deploy.

1. In the AWS Console, go to the EC2 service and find **Key Pairs** under Network & Security.
2. Create a new key pair.
   - **Name it using your Cisco username** (e.g. `jsmith-bedrock-lab`) — not something generic like "test" or "lab-key." Same goes for every other name you'll pick in this lab (the VPC name, IAM users/roles, etc.).
   - Key pair type: RSA. Private key format: `.pem` (or `.ppk` if you're a PuTTY person).
3. Create it — the private key file downloads **once**, automatically, at the moment of creation. AWS keeps no copy. Save it somewhere you won't lose it; you'll need it shortly to unlock the Windows Administrator password.

> **Why does naming matter so much here?** You're very likely sharing this AWS account with classmates going through the same lab at the same or different times. If everyone names their VPC "bedrock-lab" and their key pair "lab-key," things collide, or worse, you end up connecting to (or tearing down) someone else's box. Your Cisco username as a prefix keeps everything unambiguous and makes it obvious who owns what in a shared account.

---

## Part 3 — Deploy the Lab Environment

The lab infrastructure is defined as a CloudFormation template. Deploy it through the **CloudFormation console** (not the CLI):

1. Go to **CloudFormation → Create stack → With new resources (standard)**.
2. For the template source, choose to specify it via **Amazon S3 URL** and paste in:

   ```
   https://raw.githubusercontent.com/jlunde-cisco/SE-Onboarding-Labs/main/lab-02-bedrock-private-endpoint/cloudformation/windows-bedrock-lab.yaml
   ```

   (The field says "S3 URL" but any public HTTPS URL serving the template works — this is a raw GitHub link.)
3. Give the stack a name (again — your Cisco username somewhere in it).
4. Fill in the parameters. The two you *must* set correctly:
   - **VpcName** — use your Cisco username (e.g. `jsmith-bedrock-lab`). This flows through to the names of everything else the stack creates.
   - **MyIP** — your own public IP, in CIDR notation (e.g. `203.0.113.5/32`). This is what RDP access gets locked to, so get it right — a site like `checkip.amazonaws.com` will tell you your current public IP; append `/32`.
   - **KeyPairName** — the key pair you just created in Part 2.
   - Leave everything else at its default unless you have a reason not to.
5. Step through the rest of the wizard (nothing else needs changing) and submit.
6. Watch the stack's **Events** tab. A Windows instance takes a few minutes to come up — grab a coffee.
7. Once the stack shows `CREATE_COMPLETE`, check its **Outputs** tab for the instance's public IP address.

**What you just built:** a new VPC with a public subnet and internet gateway, a security group that only allows RDP from your own IP, and a Windows Server 2016 instance sitting in that public subnet — with Bruno already silently installed on it, so it's ready to go the moment you log in.

---

## Part 4 — Connect to Your Instance

1. In the EC2 console, find your instance, and use the **Connect** workflow to retrieve the Windows Administrator password — you'll need the key pair file from Part 2 to decrypt it.
2. RDP in using your favorite RDP client and the instance's public IP.
3. Once you're logged in, open **Server Manager** (it usually opens on its own at login). Find **IE Enhanced Security Configuration** under Local Server's properties, and turn it **Off** — at least for Administrators.

**Why bother with that last step?** Windows Server ships with Internet Explorer locked down hard by default — every site you touch triggers a security zone warning, and it'll block or nag you on things you'll want to do in this lab (referencing AWS docs, sanity-checking connectivity, etc.). Turning it off for Administrators clears that friction. Confirm it worked by browsing to a normal website without getting nagged.

---

## Part 5 — First Call to Nova Pro

Open Bruno on the instance (Bruno was pre-installed for you). Create a new request.

You're going to call the Bedrock **Runtime** API directly — not the console Playground this time. A couple of things worth knowing going in:

- There are two AWS Bedrock service endpoints that sound similar but do different things: one is for *managing* Bedrock (listing models, model access, etc.), the other — **Bedrock Runtime** — is for actually *invoking* a model. Make sure you're using the runtime one.
- The regional runtime endpoint follows a predictable pattern: `bedrock-runtime.<region>.amazonaws.com`. Swap in whatever region you deployed into.
- Bedrock Runtime supports invoking a model two ways: a model-specific "Invoke Model" path (where the JSON request body's shape depends on which model you're calling), and a newer unified **Converse** API (same request/response shape no matter which model you point it at). Either works for this lab — Converse is a bit more approachable if you're picking this up for the first time, since you don't need to know Nova's own native request schema.
- You'll need Nova Pro's exact **Model ID** — the one you recorded back in Lab 01.

Set the request method to `POST` and build the URL against the model you're calling. AWS's Bedrock Runtime API reference documents the exact path and request body shape for whichever approach you pick — go look it up rather than guessing at the JSON.

<details>
<summary><strong>Stuck on the request shape? Click for a nudge</strong></summary>

If you go the Converse route, the URL pattern is:

```
POST https://bedrock-runtime.<region>.amazonaws.com/model/<model-id>/converse
```

And a minimal request body looks like:

```json
{
  "messages": [
    {
      "role": "user",
      "content": [
        { "text": "How much wood could a woodchuck chuck if a woodchuck could chuck wood?" }
      ]
    }
  ]
}
```

Set the `Content-Type` header to `application/json`.

</details>

Don't send it yet — if you try right now, it'll fail. You haven't set up authentication. That's Part 6.

---

## Part 6 — Authenticating the Call

Every Bedrock Runtime request needs valid AWS credentials attached to it somehow — Bruno's request **Auth** tab has more than one auth type that can do this, and which one you pick depends on which method below you're using.

There are two different ways to authenticate this call. **Try both**, so you understand how each one actually works — but for the rest of this lab (and day to day, for quick manual API testing), you'll default to the long-term Bedrock API key approach for simplicity.

### Method A — IAM role attached to the instance

This is the pattern AWS generally recommends: rather than an engineer holding onto static credentials, the *instance itself* is granted permissions, and anything running on it can request temporary credentials on demand.

1. In IAM, create a role trusted by the EC2 service, with a policy that allows `bedrock:InvokeModel` (and `bedrock:InvokeModelWithResponseStream`). **Scope the `Resource` down rather than leaving it as `*`** — but if you're calling Nova Pro through the inference profile from Part 5, there's a wrinkle: see the callout right after Method B before you write this policy, since scoping it to just the plain model ARN won't be enough.
2. Attach that role to your running instance (EC2 console → your instance → change its IAM role).
3. Here's the catch: unlike the AWS CLI or an AWS SDK, Bruno has no built-in awareness of "this box has an IAM role" — it won't fetch role credentials for you automatically. You have to go get them yourself, from the **Instance Metadata Service (IMDS)**, and paste them into Bruno's auth fields by hand.
4. In Bruno, this is the one case where you want the **AWS Sig V4** auth type — role credentials are a classic Access Key ID / Secret Access Key / Session Token triple, and Bruno needs to sign the request with them the same way the AWS CLI would.

<details>
<summary><strong>Need the IMDS commands? Click here</strong></summary>

From a PowerShell prompt on the instance (IMDSv2 requires a session token first):

```powershell
$token = Invoke-RestMethod -Method PUT -Uri "http://169.254.169.254/latest/api/token" -Headers @{"X-aws-ec2-metadata-token-ttl-seconds"="21600"}
$role  = Invoke-RestMethod -Uri "http://169.254.169.254/latest/meta-data/iam/security-credentials/" -Headers @{"X-aws-ec2-metadata-token"=$token}
Invoke-RestMethod -Uri "http://169.254.169.254/latest/meta-data/iam/security-credentials/$role" -Headers @{"X-aws-ec2-metadata-token"=$token}
```

The last command returns JSON with `AccessKeyId`, `SecretAccessKey`, and `Token` — those map to Bruno's Access Key ID / Secret Access Key / Session Token fields. Note the `Expiration` field too — these are temporary.

</details>

### Method B — A Bedrock API key (the default for this lab)

Bedrock has its own dedicated, built-in API key feature — this is a distinct mechanism from a generic IAM user access key, and it's worth not conflating the two. It's purpose-built for exactly what you're doing right now: quickly authenticating a manual API call without setting up IAM users, policies, or SigV4 signing yourself.

1. In the **Bedrock console** (not IAM), find **API keys** in the left navigation.
2. Switch to the **Long-term API keys** tab and generate one — you'll pick an expiration date for it (it's "long-term" relative to the other option below, not indefinite). By default it comes with a managed policy attached that covers general Bedrock access, so you don't need to write a policy yourself just to get started — though stick around for the callout further down; inference profiles specifically add a wrinkle even here.
3. The key is shown to you **once** — copy it immediately, same as everything else in this lab.
4. In Bruno, this one is simpler than Method A: switch the Auth type to **Bearer Token** and paste the key in directly. That's it — no Access Key ID, no Secret Access Key, no signing. Under the hood this still creates an IAM user and something AWS calls a "service-specific credential," but you never have to touch that directly the way you did in Method A.

Now send your request from Part 5 using this auth method. You should get a real response back from Nova Pro... probably. Keep reading before you panic if you don't.

> **Bonus, not required for this lab:** there's also a **short-term** Bedrock API key option on that same page — it inherits whatever permissions your current console session already has, and expires within 12 hours. It's the option AWS actually recommends once you're past "just exploring" and building something real. Worth knowing it exists, since the "long-term key, forever, why would I rotate it" habit is exactly the kind of thing that gets flagged in a real security review.

### If Nova Pro pushes back

If you built your request URL using Nova Pro's plain Model ID (the one you recorded in Lab 01), don't be surprised if what comes back isn't a completion at all, but something like this:

```json
{
  "message": "Invocation of model ID amazon.nova-pro-v1:0 with on-demand throughput isn’t supported. Retry your request with the ID or ARN of an inference profile that contains this model."
}
```

Before you assume you botched the request or the auth — you didn't. This is Bedrock telling you something specific and real: some models (Nova Pro among them) can't be invoked on-demand by their plain model ID at all. They can only be invoked through an **inference profile** — a Bedrock construct that (among other things) can route your request across multiple regions for capacity. Bedrock won't guess which profile you mean, so it makes you say so explicitly.

Head into the Bedrock console and look for **Inference profiles** in the left navigation (under the "Infer" section). On the **System-defined** tab, filter/search for a profile whose model is Nova Pro, and grab its **Inference profile ID** (or ARN). Then swap that value into your request URL in place of the plain model ID you were using before, and resend.

<details>
<summary><strong>Not finding it / want a sanity check on the format?</strong></summary>

Inference profile IDs generally follow a `<region-group>.<original-model-id>` pattern — for example `us.amazon.nova-pro-v1:0` for the US region group (this one specifically routes across `us-east-1`, `us-east-2`, and `us-west-2`). The exact prefix depends on which region group covers where you deployed, so confirm the real value against what the console actually shows you rather than assuming the `us.` prefix is universal.

</details>

### One more wrinkle: permissions on the inference profile itself

Fixed the URL and still getting denied? You might hit an error like this next:

```json
{
  "Message": "User: arn:aws:iam::<account-id>:user/<your-user> is not authorized to perform: bedrock:InvokeModel on resource: arn:aws:bedrock:<region>:<account-id>:inference-profile/us.amazon.nova-pro-v1:0 because no identity-based policy allows the bedrock:InvokeModel action"
}
```

That specific phrasing — *"because no identity-based policy allows..."* — is IAM's wording for a plain missing permission, not something actively blocking you. Here's the real gotcha: **invoking a model through an inference profile requires permission on both the inference-profile ARN *and* the underlying foundation-model ARN in every region that profile can route to** — not just one or the other. AWS's own documentation calls this out explicitly. If whatever identity you're using only has permission scoped to the plain model ARN (or, depending on what's attached to it, doesn't cover inference profiles at all), this is exactly the error you'll get.

The fix is an Allow statement covering both ARN shapes — for Nova Pro's US profile specifically, that means the profile ARN plus the foundation-model ARN in each of the three regions it spans:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowNovaProViaInferenceProfile",
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel*",
      "Resource": [
        "arn:aws:bedrock:<region>:<account-id>:inference-profile/us.amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-east-2::foundation-model/amazon.nova-pro-v1:0",
        "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-pro-v1:0"
      ]
    }
  ]
}
```

Attach this as an inline policy to whichever identity you're using (the role from Method A, or — if Method B's default managed policy doesn't already cover inference profiles — the IAM user behind your Bedrock API key).

While you're troubleshooting this, worth also knowing: **`bedrock:Converse` is not a real, separate IAM action**, even though it looks like it should be one. If you tried adding it to a policy and IAM's console rejected it, that's correct behavior, not a bug on your end — the Converse API is authorized under the same `bedrock:InvokeModel` action as the older Invoke API. `bedrock:InvokeModel*` (the wildcard form used above) covers both `InvokeModel` and `InvokeModelWithResponseStream` in one line.

### Reflect

You've now authenticated the same API call two different ways. Before moving on, think through: what's actually different about these two credential types, and why might one be preferred over the other in a real production system versus a quick local API-testing tool like Bruno?

<details>
<summary><strong>Click to reveal</strong></summary>

**Role-based credentials are temporary and tied to the instance's lifecycle.** There's no long-lived secret sitting around to leak — if the credentials are ever exposed, they expire on their own (often within hours), and nobody had to type or store a permanent secret anywhere. This is why AWS (and most security teams) push hard for roles wherever the *tooling* supports it: the AWS CLI, SDKs, and most infrastructure code all know how to fetch and refresh role credentials from IMDS transparently.

**A long-term Bedrock API key is simple but comparatively static.** It works anywhere, including tools like Bruno/Postman that have no concept of "ask the instance for temporary creds" — you just paste in a value and it works, no signing, no expiration to worry about mid-request. The tradeoff is that a leaked long-term key stays valid until it either expires (on whatever schedule you picked when you generated it) or someone manually revokes it. That's exactly why this lab defaults to it: it's the practical choice for a manual API-testing tool, not a security recommendation to carry into production service-to-service code — AWS's own documentation for this feature says as much, explicitly recommending short-term keys once you're building something real rather than just exploring.

</details>

---

## Part 7 — Going Private: Routing Through a VPC Endpoint

Right now, your call to `bedrock-runtime.<region>.amazonaws.com` travels out through the instance's internet gateway, across the public internet, to AWS. This section walks you through forcing that same call over **AWS PrivateLink** instead — so it never leaves AWS's network. This part is more heavily guided than the rest of the lab; the concepts (interface endpoints, private DNS, security group egress) are worth understanding, not rediscovering from scratch.

### Step 1 — Confirm today's baseline: this is genuinely public

Before you lock anything down, prove to yourself that what you have right now really is public — not "public in some theoretical sense," but reachable from literally anywhere with valid credentials.

1. On the Windows instance, open a command prompt and run:

   ```
   ping bedrock-runtime.<region>.amazonaws.com
   ```

   Swap in whatever region you deployed into. Don't be thrown if the actual echo requests time out — plenty of AWS service endpoints don't answer ICMP at all. The part you actually care about is the first line, which shows the IP address the hostname resolved to (something like `Pinging bedrock-runtime.us-east-2.amazonaws.com [x.x.x.x]`) — that's an ordinary public AWS IP, nothing PrivateLink-related yet.

2. Now switch to a machine that has nothing to do with this lab's VPC at all — your actual laptop, wherever you normally work. Open Bruno (or Postman, or whatever's installed there) and send the exact same authenticated Nova Pro request you built in Parts 5 and 6 — same URL, same body, same credentials.

   It should just work, no differently than it did from the lab instance. No VPC, no security group, no proximity to AWS infrastructure of any kind required — just valid credentials and an internet connection. That's what a "public endpoint" actually means, and it's exactly what the rest of this section changes — but only for traffic leaving your lab instance, as you'll see at the end.

### Step 2 — Create the interface VPC endpoint

Before you create the endpoint itself, add one security group rule to get out of the way of a very common gotcha: create (or pick) a security group for the endpoint and add an inbound rule allowing **HTTPS (443) from anywhere (0.0.0.0/0)**. Yes, "anywhere" — that's intentional, and less alarming than it sounds: this endpoint's network interface only gets a *private* IP with no route in from the public internet, so "anywhere" in practice only ever means "anywhere inside this VPC that can already route to it." Opening it this wide sidesteps a fiddly failure mode: if you instead try to scope the source down to "the instance's security group" and get the reference wrong — or, easy to do by accident, leave the endpoint on the VPC's **default** security group — connections will silently time out. AWS's default security group only allows traffic between resources that are *also* members of that same default security group, which your lab instance isn't, so it doesn't cover this at all.

1. In the VPC console, go to **Endpoints → Create endpoint**.
2. Service category: AWS services. Search for and select the **Interface** endpoint for `bedrock-runtime` in your region.
3. VPC: your lab VPC. Subnet: the lab's public subnet (it's the only one you have).
4. **Enable DNS name** (private DNS) — this is the setting that makes the standard `bedrock-runtime.<region>.amazonaws.com` hostname resolve to the endpoint's private IP instead of a public one, so you don't have to change your Bruno request's URL at all.
5. Security group: attach the one you just set up above (443 from anywhere), not the VPC's default security group.
6. Create the endpoint and wait for it to become available.

If you'd rather scope the inbound rule down more tightly (source = your instance's security group specifically, instead of 0.0.0.0/0) once you've got the basic flow working, that's a reasonable thing to circle back and try — just know it's the part most likely to leave you stuck with a silent timeout if the reference doesn't line up exactly right.

### Step 3 — Verify DNS is actually resolving privately

Back on the Windows instance, open a command prompt and run:

```
nslookup bedrock-runtime.<region>.amazonaws.com
```

Compare this against what the `ping` in Step 1 showed you. Now, with private DNS enabled, it should resolve to a private address inside your VPC's CIDR range instead of the public IP you saw before. If it's still showing a public IP, double check the endpoint's "Enable DNS name" setting and give DNS a minute to catch up.

### Step 4 — Actually force the private path

Here's the part that's easy to miss: **just creating the endpoint doesn't stop the instance from also being able to reach the internet directly.** Private DNS changes what address the hostname resolves to, but your instance's security group still has a default "allow all outbound" rule — so traffic *could* still leave over the internet through some other path. To genuinely guarantee this traffic stays private, you need to close that door:

1. Edit your instance's security group's **outbound** rules.
2. Remove the default rule that allows all outbound traffic.
3. Add a scoped rule that allows outbound HTTPS (443) only to the VPC endpoint's security group (or to your VPC's CIDR range).

Expect this to also block other outbound HTTPS traffic from the box (general web browsing, Windows Update, etc.) — that's expected and fine for the lab; you can always revert the rule if something breaks and you need internet access back.

### Step 5 — Re-test

Send your Nova Pro request from Bruno again, unchanged. It should still succeed — but now via PrivateLink instead of the internet.

If you go back to your own laptop from Step 1 and send that same request again from there, it'll still work too, completely unaffected. That's worth sitting with for a second: you haven't made Bedrock itself private, or even this specific model private. You've only forced *this one VPC's* path to Bedrock over PrivateLink. Anyone else with valid credentials, anywhere else on the internet, still reaches the exact same public endpoint you did back in Step 1.

### Reflect

<details>
<summary><strong>Why did we have to touch the security group at all — isn't enabling private DNS enough?</strong></summary>

Private DNS only controls what IP address a hostname *resolves to*. It doesn't, by itself, prevent your instance from reaching the internet through some other means — a different DNS server, a hardcoded IP, or just the fact that your security group still had a wide-open outbound rule. If you only cared about the *happy path* working, DNS alone would look like enough — your request would go to the right place. But the actual goal here is guaranteeing this traffic **can't** leave over the public internet, and that guarantee only comes from also cutting off the network path itself. This is a good general lesson: DNS-based routing convenience and hard network-level enforcement are two different things, and "it happens to work" isn't the same as "it's actually private."

</details>

---

## Part 8 — Making It *Actually* Private

Part 7 ended on a deliberately unsatisfying note: you forced your lab instance's own traffic over PrivateLink, but the credentials themselves — that Bedrock API key, or the role's temporary creds — would still work perfectly well if used from anywhere else on the internet. Locking down *your instance's network path* is not the same thing as locking down *the model*. So: how do you actually close that gap, so those specific credentials stop working the moment they leave your VPC — even if they leak, even if someone copies them onto their own laptop?

The mechanism is an IAM condition key called **`aws:SourceVpce`**. AWS automatically attaches this to the request context of any API call that arrives through a VPC endpoint — and it's simply *absent* for anything that doesn't. That means you can write an explicit `Deny` statement on the identity making the call that says, in effect, "block this unless the request came in through this exact endpoint." Since that condition only ever gets populated for endpoint traffic, there's no way to satisfy it from outside your VPC — not with a copy of the credentials, not from a different account, not from anywhere.

1. Grab your VPC endpoint's ID (it starts with `vpce-`) from its detail page in the VPC console.
2. In IAM, find the identity behind whichever auth method you're actively testing with — the role from Method A, or (remember, from Part 6, that a long-term Bedrock API key is backed by an IAM user under the hood) that user, if you went with Method B.
3. Attach an inline policy to it with a statement like this (swap in your real endpoint ID):

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Sid": "DenyBedrockUnlessViaMyEndpoint",
         "Effect": "Deny",
         "Action": "bedrock:InvokeModel*",
         "Resource": "*",
         "Condition": {
           "StringNotEquals": {
             "aws:SourceVpce": "vpce-xxxxxxxxxxxxxxxxx"
           }
         }
       }
     ]
   }
   ```

   Notice the `Resource` here is `*`, not scoped down to Nova Pro specifically — deliberately, since a Deny like this is meant to be a blanket network guardrail, not a fine-grained permission. You don't want a gap where some other model ARN quietly slips through ungoverned. And `bedrock:InvokeModel*` (a wildcard, not a literal action name) is intentional too — it covers both `InvokeModel` and `InvokeModelWithResponseStream` in one line, including whatever's authorizing your Converse calls under the hood, without needing a separate `bedrock:Converse` action (which — as you may have discovered back in Part 6 — isn't actually a real, distinct IAM action at all).

4. Retest from your own laptop, outside the VPC — the exact same request and credentials that worked back in Part 7. It should now fail with an access-denied-style error.
5. Retest from the lab instance. It should still succeed — that traffic carries the matching `aws:SourceVpce` context, so the Deny's condition doesn't trigger.

If something goes sideways, this policy is easy to back out of — it's an inline policy on one identity, not a change to the console session you're working in, so removing it undoes exactly this.

### Reflect

<details>
<summary><strong>What's genuinely different about this vs. what Part 7 did?</strong></summary>

Part 7 controlled *your instance's* side of the network path — it changed how traffic leaving that specific box gets to Bedrock, but it never touched whether the credentials themselves would work from somewhere else entirely. This Deny statement controls the credential at the authorization layer, regardless of whose infrastructure is making the call. That's the actual difference between "my traffic happens to take a certain route" and "these specific credentials are only valid when arriving via one particular path" — and it's the real answer to "how do I stop a leaked key from being usable to reach this model over the internet."

One honest caveat, though: this only restricts the identity you attached it to. It doesn't make Bedrock's public endpoint vanish for the rest of the world — other AWS accounts, and any of *your* other credentials you didn't lock down this way, can still reach it exactly as before. What you've actually achieved is narrower and more useful than "made a model private" sounds: you've made a *specific set of credentials* incapable of reaching Bedrock from anywhere except your own private network path. For defending against a leaked key or a misused role, that's precisely the guarantee that matters.

</details>

---

## Wrap-Up

Before moving on, make sure you can answer these:

1. Why did the lab have you name everything after your Cisco username instead of something generic?
2. What's the difference between the Bedrock control-plane endpoint and the Bedrock **Runtime** endpoint?
3. Walk through, in your own words, how an EC2 instance role actually gets Bruno a usable set of credentials — what's happening under the hood that the AWS CLI would normally do for you automatically?
4. What's genuinely different between a long-term Bedrock API key and IAM role credentials fetched from IMDS — not just "how you use them in Bruno," but what each one actually *is*?
5. Why did calling Nova Pro by its plain Model ID fail, and what did you have to use instead? Why do you think Bedrock enforces this for some models and not others?
6. What two things had to both be true before your Bedrock traffic was genuinely private, not just "happens to resolve to a private IP"?
7. After Part 8, if someone stole the exact credentials you were using and tried them from their own laptop, what would happen — and what would happen if they instead got access to a machine inside your VPC? What does that tell you about what `aws:SourceVpce` actually protects against?

Ping your onboarding buddy or the team channel if any of this didn't click — this lab covers real production patterns (private endpoints, least-privilege IAM, role vs. key tradeoffs, and closing the gap between "private-ish" and actually enforced), not just Bedrock trivia.
