# Usability test script (5 participants)

**Goal:** find out whether people who have never seen the system can report a problem and
follow it up without help, on their own phone.

**Who:** 5 adults who live or work in Murang'a (or anywhere in Kenya), who have **not** seen the
app. Aim for a mix: at least two over 45, at least one who mainly uses Kiswahili or Gĩkũyũ, and at
least one with a basic or older Android phone. Five people find most of the serious problems
(Nielsen & Landauer, 1993); a sixth adds little.

**Where and how long:** in person or on a video call with screen sharing, 20–25 minutes each.
Use the deployed site on the participant's own phone and mobile data, not Wi-Fi if possible.

**You need:** this script, `results.md` (one copy per participant), a timer, and the
demo officer login (to move a test case along during task 4).

---

## 1. Introduction (read aloud, ~2 min)

> Thank you for helping. We're testing a website, not you. There are no wrong answers, and if
> something is confusing, that's exactly what we need to know. Please think aloud: say what
> you're looking at, what you expect and what surprises you. I won't help during the tasks,
> because I want to see how the site works on its own; if you're truly stuck, say "I'd give up
> here" and we'll move on. I'll take notes but won't record your name or number. The account
> you create is a test account, and I'll delete it afterwards. Is that all right?

Get verbal consent. Note the phone model and the browser.

## 2. Tasks

Read each task card aloud, then hand over or show it. Start the timer when they start and
stop it when they say they're done or give up. **Don't** say the names of buttons or menus.

| # | Task card (read exactly) | Success means |
|---|---|---|
| 1 | "You've heard you can report problems to the county on this website. Create an account for yourself." | Account created and signed in. |
| 2 | "The streetlight outside your gate has been off for three nights. Report it." (Ask them to imagine they're standing at the light.) | A streetlight report submitted with a location and a description. |
| 3 | "A week later, you want to know whether anyone is working on it. Find out." | Opens their report and says its status out loud. |
| 4 | *(Before this task, sign in as the officer on your own device and move their case to Resolved with a note.)* "You got a message saying it's fixed. You walk past and it's still off. Tell the county." | Reopens the case with a reason. |
| 5 | "Your neighbour says they already reported a water leak at the corner. Before reporting it yourself, check whether it's already reported." *(Before the session, report a water leak somewhere and give them its rough location.)* | Reaches the "Is it one of these?" step and follows the existing report instead of filing a duplicate. |

## 3. Probes after each task (only after it's finished)

* "What did you expect to happen when you tapped …?"
* "Was there anything you weren't sure about?"
* "On a scale of 1 (very hard) to 5 (very easy), how was that?"

## 4. Closing (~3 min)

* "What, if anything, would stop you from using this for real?"
* "Is there a word on the screens you didn't understand?"
* "Would you prefer the site in Kiswahili?"

Thank them. Afterwards, delete their test account (Django admin → Users) and their reports, if
you're not keeping them for the next participant.

## 5. Recording findings

For each participant, fill in `results.md`. Then, for each **issue** (anything that
slowed someone down, confused them, or made them fail), rate the severity:

| Severity | Meaning |
|---|---|
| 3 – Critical | Stopped the participant completing the task |
| 2 – Serious | Completed, but only after a long delay or a wrong path |
| 1 – Minor | Hesitation or a comment, no real delay |

An issue seen with 2 or more participants, or any severity 3, gets fixed before the next round.
List each fix in `results.md` under "What changed", with the commit that fixed it.
