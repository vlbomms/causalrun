# Installable skill evidence

Command: `python3 -m tests.run_skill`.

100 tests passed; zero failures, errors, or skips. Four new tests check skill-only
installation without config changes, refusal to overwrite an unrelated skill,
standalone zipapp packaging, and actual OpenCode global skill discovery.

Three actual OpenCode session checks passed. The host received an ordinary request
without the word causalrun, advertised the skill in its system prompt, and loaded
it through its native skill tool. The scripted fixture then exercised rule approval,
a lost write response, read recovery, host/runtime restart, and new-session startup.
The independent controlled provider recorded one write and one object throughout.

- [Tests, versions, and execution hashes](tests.json)
- [Full output](tests.txt)
- [Final host messages, skill discovery, approval, and timelines](host.json)
- [First failed host check](host-attempt-1.json)
- [Second failed diagnostic host check](host-attempt-2.json)
- [First successful focused host check](host-attempt-3.json)
- [Initial frontmatter validator mismatch](validation-attempt-1.json)

The failed host checks expected the skill catalog in the tool description. OpenCode
1.18.34 puts it in the system prompt. The test now checks both supported locations
and requires a completed native skill load. The shared validator also rejected
OpenCode's optional top-level compatibility field; moving it into metadata retained
compatibility with both formats. These failed checks remain in the record.

The model was scripted and explicitly selected the advertised skill. This verifies
packaging, discovery, loading, and the execution path; it does not prove that a live
model always selects the skill for ordinary requests. Shell writes remain a bypass.
No real GitHub writes or paid inference occurred in this work.
