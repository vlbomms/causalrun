# Clear language

causalrun uses ASD-STE100 writing rules for its fixed user messages.
The OpenCode plugin also gives these rules to the agent in every session:

- Use short sentences and active voice.
- Give one instruction in each sentence.
- Use no more than 20 words in an instruction.
- Use no more than 25 words in a description.
- Use one term for each item.
- Give the result first. Give the next step only when it is necessary.

Use these terms in user messages:

| Technical name | User term |
| --- | --- |
| connector | write rule |
| verifier | result check |
| COMMITTED | The write is confirmed. |
| IN_DOUBT | The result is unknown. Do not send the write again. |

Normal updates have no more than three sentences. Do not repeat hashes, source
code, or full records in chat. Preserve API names, code, paths, and user content.
These items are technical data, not prose to rewrite.

The permission summary shows the target, result condition, test count, and limits.
The full review file contains the exact source, contract, and validation report.
Read that file before approval. Its file name binds both content hashes.
The runtime also retains those records in SQLite.

Full action records are available through `causalrun_result` with `details=true`.
The default output keeps the original action ID and state. It does not show the
full receipt or journal.

Tests check the fixed messages and output size. The plugin directs model replies
but does not run a second model to rewrite them. It cannot certify every reply
against the complete controlled dictionary and its grammar rules.
See the official [ASD-STE100 explanation](https://www.asd-ste100.org/about_STE.html)
and [FAQ](https://www.asd-ste100.org/STE_faq.html).
