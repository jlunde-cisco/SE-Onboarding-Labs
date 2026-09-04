# Lab 01 — Connecting to AWS & Exploring the Bedrock Playground

## What you'll learn

By the end of this lab you'll be able to:

- Get into an AWS account and find the Bedrock service
- Read a model's entry in the Bedrock Model Catalog and pull out the specs that actually matter
- Run the same prompt against two different models side-by-side in the Playground
- Explain *why* two models can give you different token counts and latency for the identical question
- Use the model settings (temperature, max tokens) to change how a model behaves

Don't rush to the answers. The point of this lab is to click around, notice things, and form your own hypothesis before checking it. Every section below tells you *where to go and what to look for* — figuring out the exact clicks is part of the exercise.

---

## Prerequisites

- **An AWS account with Bedrock access.** If you don't have one:
  - Cisco folks: you can look up the AWS accounts you already have access to at **https://go2.cisco.com/aws**
  - If you still don't have an account, email **jlunde@cisco.com** and I'll get you added.
- A modern browser and about 45–60 minutes.

---

## Part 1 — Get Connected

1. Sign in to your AWS account.
2. Once you're in the console, find your way to the **Amazon Bedrock** service. (Top search bar is your friend.)
3. Take note of what **region** you land in. Bedrock's available models can differ from region to region — if you don't see a model mentioned later in this lab, that's the first thing to check.
4. Look around the left-hand navigation for a minute before moving on. You should be able to spot something called the **Model catalog** and something called the **Playground** (it may be nested under a "Playgrounds" or "Chat / Text playground" section). We'll use both.

---

## Part 2 — Model Catalog Recon

Head into the **Model catalog**. Find these two models:

- **Amazon Nova Pro**
- **OpenAI GPT-5.6 Luna v1**

Click into each model's detail page and fill out the table below. All of this information is on the page somewhere — you're just hunting for it.

| Attribute | Nova Pro | GPT-5.6 Luna v1 |
|---|---|---|
| Model ID |  |  |
| Provider |  |  |
| Deployment type (On-demand? Provisioned throughput? Both?) |  |  |
| Inference type (text, chat, multimodal, etc.) |  |  |
| Max input tokens (context window) |  |  |
| Max output tokens |  |  |

**Things to notice while you're in there:**

- Deployment type matters a lot in real projects — some models are *only* available with provisioned throughput, which changes how you'd architect around them and what they cost.
- "Max output tokens" and "context window" are not the same number, and it's easy to conflate them. Make sure you know which is which for each model.
- The **Model ID** is the string you'd actually reference in code (via the Bedrock API/SDK) — it's worth knowing where to find it, since it rarely matches the friendly marketing name exactly.

---

## Part 3 — Head-to-Head in the Playground

1. Open the **Playground** and find the option to compare multiple models at once (Bedrock supports putting two models side by side in the same view).
2. Load up **Nova Pro** and **OpenAI GPT-5.6 Luna v1** together.
3. Send both the exact same prompt:

   > How much wood could a woodchuck chuck if a woodchuck could chuck wood?

4. Let both models respond, then find where the Playground reports **input tokens**, **output tokens**, and **latency** for each response. (Look near/under each response — Bedrock usually surfaces this as metadata you may need to expand.)

Record what you see:

| Metric | Nova Pro | GPT-5.6 Luna v1 |
|---|---|---|
| Input tokens |  |  |
| Output tokens |  |  |
| Latency (ms) |  |  |

For reference, here's what I got when I ran this exact test:

| Metric | Nova Pro | GPT-5.6 Luna v1 |
|---|---|---|
| Input tokens | 16 | 24 |
| Output tokens | 192 | 72 |
| Latency (ms) | 1665 | 1052 |

Your numbers won't match mine exactly (models are non-deterministic, and Nova's answer length in particular can vary run to run) — but the *pattern* should look similar.

### Now ask yourself: why are these numbers different?

Same prompt, same question, sent at the same time. So why the gap in input tokens, output tokens, and latency? Spend a couple minutes actually thinking about this — what would need to be true for the *input* token count to differ if the prompt text was identical? What would explain one model's output being over 2x longer than the other's? Does latency track with anything else in the table?

Write down your own theory before you expand the answer below.

<details>
<summary><strong>Click to reveal an explanation</strong></summary>

**Input tokens differ even though the prompt was identical.** Every model provider tokenizes text with its own tokenizer/vocabulary. "How much wood could a woodchuck chuck..." gets chopped into tokens differently depending on the model's tokenizer, so the *same string* produces a different token count. There's also often a small amount of provider-specific formatting/system scaffolding wrapped around your prompt before it reaches the model, which can add a few tokens.

**Output tokens differ because the models genuinely answered differently.** This is a classic "tongue twister" style riddle. Some models will give a short, direct answer; others (Nova Pro here) tend to be more explanatory/conversational by default — walking through the wordplay, maybe citing the famous "as much wood as a woodchuck would..." folk answer, adding caveats, etc. That verbosity is a genuine behavioral difference between models, not a bug — some model families are just tuned to be chattier by default.

**Latency mostly tracks with output length, but not only that.** Generating tokens takes time — a response with 192 output tokens has more generation work to do than one with 72, so you'd expect it to take longer, all else equal. But latency is also affected by the model's architecture/size, current load on the provider's infrastructure, and — going back to Part 2 — its **deployment type**. A model backed by shared on-demand capacity can behave differently under load than one backed by dedicated provisioned throughput. So when you compare latency across models, output length is a big factor, but it's not the *only* factor.

The takeaway: token counts and latency aren't just "how good" a model is — they're a mix of tokenizer differences, the model's default verbosity/tuning, and how it's deployed. Keep that in mind any time you're comparing models on cost or speed.

</details>

---

## Part 4 — Model Settings: Temperature & Max Tokens

1. Back in the Playground, find the **settings toggle/panel** for one of the models (it's usually a gear icon or a collapsible "Inference configuration" section next to the chat).
2. You should find at least two controls worth experimenting with:
   - **Maximum output tokens (max tokens)**
   - **Temperature**
3. Try the following experiments — you can reuse the woodchuck prompt or come up with your own (a creative-writing prompt tends to show temperature effects more clearly than a factual one):

   - **Lower the max tokens** to something small (e.g., 20–30) and re-run a prompt that normally produces a long answer. Watch what happens to the response — does it finish its thought, or does it just stop mid-sentence?
   - **Set temperature to something very low (near 0)** and run the *same* prompt two or three times. Compare the responses.
   - **Set temperature high (near the max the slider allows)** and run that same prompt two or three times again. Compare.

**Things to notice and think about:**

- What does a truncated response (from a low max-token limit) actually look like? Is there any indication in the UI that the response got cut off, versus the model just deciding to stop?
- At low temperature, how similar are the repeated runs to each other? At high temperature?
- Does temperature seem to affect the *length* of the response, or mainly the *wording/creativity*? What does that tell you about what temperature is actually controlling?
- If you were building something that needed consistent, repeatable output (e.g., generating structured data), which temperature setting would you reach for? What about a brainstorming or creative-writing assistant?

---

## Wrap-Up

Before you move to the next lab, make sure you can answer these in your own words:

1. Where do you go in the AWS console to find available foundation models, and where do you go to actually chat with one?
2. What's the difference between a model's **deployment type** and its **inference type**?
3. Name two reasons two different models could report different token counts for the same input prompt.
4. What does **max output tokens** control, and what does **temperature** control? How are they different?

Ping your onboarding buddy or drop questions in the team channel if anything felt unclear — this lab is meant to build intuition, not just check a box.
