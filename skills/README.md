# OhMyCaptcha Skills

This repository includes reusable skills for Claude Code, OpenCode, OpenClaw-style workflows, and similar agent environments.

## Included skills

- `skills/ohmycaptcha/` — deploy, validate, and integrate OhMyCaptcha
- `skills/ohmycaptcha-image/` — generate public-safe visuals for README and docs

## For humans

Copy one or both of these folders into your local skills directory:

```text
skills/ohmycaptcha/
skills/ohmycaptcha-image/
```

Then restart your tool if it caches skills.

## Let an LLM do it

Paste this into any capable LLM agent:

```text
Install the OhMyCaptcha skills from this repository and make them available in my local skills directory. Then show me how to use the operational skill for deployment and the image skill for generating README or docs visuals.
```

## Notes

- Both skills are documentation-backed.
- Both skills use placeholder credentials only.
- The image skill is designed for repository-safe artwork and prompt generation.
