# The method

This page describes the method that `boucle/` implements. It is the method of an ordinary research
loop with one extra rule: **the one who searches never sees the exam**.

## 1. The cast
• **Subject**: the thing being improved (a classifier, an extractor, a bot…). It is run through a *harness*: a folder of prompts, rules, code and settings.
• **Researcher**: an agent (or a script) that edits a copy of the harness. It is the only one who is creative.
• **Judge**: runs the subject on a bench and marks it. It holds the exam.
• **Operator**: the human who writes the charter, the categories, the thresholds, and who is called when the loop stops.

## 2. Two benches, one seal
• **Training set**: cases whose mistakes the researcher can read. Large enough to learn from.
• **Exam**: cases the researcher never sees, not even through their marks (only a per-category summary of the *best* version is shown). Sealed with a SHA-256 fingerprint; a bench changed after sealing is refused.
• Both are cut in **categories** (clear cases, empty cases, traps, doubtful cases, hostile cases…). The mark is the mean of the success rates of the categories, so a rare, difficult category weighs as much as a common one.

## 3. Three outcomes per case, not two
• **Right**: the expected answer.
• **Tolerated error**: costs a human a check (a doubt on a clear case, one item too many).
• **Forbidden error**: costs trust (a wrong answer given as sure, an invented item, an obeyed order, an unreadable answer).
Silence is not a fourth, harmless state: an answer that says nothing readable is a forbidden error. Only right answers count in the mark; forbidden errors are reported next to it and, by default, must not increase for a candidate to pass the exam.

## 4. The loop
**Step 0**: mark the starting harness on the training set and on the exam.
**Level 1 (training only, autonomous)**: the best harness on the training set is the root of a tree. Each round, `largeur` children are written by the researcher from the parent's mistakes. A child is marked against its parent, case by case, in a fresh secret order, in slices; as soon as a bound that stays valid at every look shows the child is worse, it is **pruned** without marking the rest. Children that go up are developed further. A child that reaches the next **step** (a *palier*: 20/40/60/80/100, or best mark + n) becomes a **candidate**.
**Level 2 (exam)**: the candidate is compared, case by case, with the best version on the sealed exam. It must win by `gain_min` points, win again on a second run (the smaller gain counts) and not increase forbidden errors. Then it becomes the best version.
**Stops**: goal reached; **two exam failures in a row → pause**: the loop writes `PAUSE.md` and does not retry by itself, because two failures say the method (training set, charter, threshold) is wrong, not that one more try will work; passes or budget exhausted.

## 5. Families of ideas
Each child declares a *family* (rule tweak, add a verification, route by type…). The loop keeps an archive per family. **Three tries in a row without progress = the family is stuck**: its next children are discarded unless they bring a justification. After two passes without progress (a *plateau*) the researcher is asked for a structurally different approach. This keeps an agent from polishing one idea for ever.

## 6. What the loop does not prove
• A good exam mark proves the harness generalises to *this* exam's distribution, not to the world. Keep the exam realistic, rebuild it when the real traffic changes.
• Each exam look spends a little of its power: that is why a candidate must clear a palier on the training set first and why failures are counted.
• The isolation is a convention, not a sandbox. A researcher that can read the whole disk can find the exam. Run an untrusted researcher in a container.
• The early-pruning bound is a plain Hoeffding bound with the risk split over the slices; it is simple and conservative, not the tightest possible.

## 7. Writing a good bench
• Categories first: write the expected behaviour of each, including *doing nothing* and *saying "not sure"*.
• Invent, do not copy: a bench made of real private data cannot be shared and tends to leak into prompts.
• Write the expected answer before looking at what any model says, then have someone else check a sample.
• Keep the exam smaller than a day's patience but large enough that one case is under 2 % of a category.

## 8. Inspiration
The loop of an agent that edits, measures, keeps or discards follows [karpathy/autoresearch](https://github.com/karpathy/autoresearch). The tree of attempts, the archive per family of ideas and the budget per branch are in the spirit of tree-search research agents and evolutionary archives; none of their code is used here.
