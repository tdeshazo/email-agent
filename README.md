# Email Agent

Small Python agent that reviews recent Gmail messages with Ollama and sends important ones to Discord as webhook embeds.

## Motivation

Newsletters, promos, and automated alerts quickly bury the few emails that actually matter, especially recruiter outreach, interview scheduling, and application updates. This project keeps Gmail as the source of truth while adding a lightweight “last-mile” notification layer that surfaces only high-signal career emails to Discord via webhooks.

## What It Doess

- Reads messages from Gmail (`gmail.readonly` scope).
- Prompts model to decide whether each email is important.
- Uses a `notify` tool call to create one Discord embed per important email.
- Queues all embeds and sends them after processing completes.
- Auto-chunks webhook sends to Discord's embed limit (10 embeds per webhook message).

## Requirements

- Python 3.10+
- Gmail API OAuth desktop credentials (`credentials.json`)
- Running Ollama API endpoint
- Discord webhook URL

## Installs

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional: install as a package (adds `email-agent` CLI).

```bash
pip install -e .
```

## Configuration

Set these environment variables (or place them in `.env` if `python-dotenv` is installed):

```env
OLLAMA_CHAT_URL=...
OLLAMA_MODEL=llama3.1
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

System prompt lookup order:

1. `~/.email-agent/EMAILS.md`
2. `./EMAILS.md`
3. `./prompts/EMAILS.md`

## Gmail Setup

1. Enable the Gmail API in Google Cloud.
2. Create an OAuth client for a desktop app.
3. Download the OAuth JSON and save it as `credentials.json` in the project root.
4. On first run, complete the browser auth flow; `token.json` will be created automatically.

## Run

```bash
PYTHONPATH=src python -m email_agent.cli
```

If installed with `pip install -e .`:

```bash
email-agent
```

Optional: override the message receipt window used for `GmailReader.get_messages(..., time_delta=...)`:

```bash
PYTHONPATH=src python -m email_agent.cli --time-delta 30m
PYTHONPATH=src python -m email_agent.cli --time-delta 2h
PYTHONPATH=src python -m email_agent.cli --time-delta 1d
```

## Current Processing Behavior

- Query starts with: `newer_than("1d").in_("inbox")`.
- Reader fetches up to 50 messages.
- Additional time filter keeps only emails received in the last hour by default (`--time-delta` overrides this).
- Prompt includes sender, subject, snippet, and body preview (first 700 chars).
- After all emails are reviewed, queued embeds are sent to Discord in batches of 10.

## Project Files

- `src/email_agent/cli.py`: argument parsing and runtime orchestration.
- `src/email_agent/config.py`: dotenv loading and prompt file resolution.
- `src/email_agent/service.py`: email triage workflow.
- `src/email_agent/clients/gmail_client.py`: Gmail auth, query builder, message wrappers.
- `src/email_agent/clients/ollama_client.py`: Ollama chat/tool-call API client.
- `src/email_agent/clients/discord_client.py`: Discord embed and webhook logic.
- `prompts/EMAILS.md`: project prompt template.

## Notes

- `token.json` and `credentials.json` are local secrets and should not be committed.
- If no emails are marked important, no webhook request is sent.
- You will need to customize prompts for your use case.

## Roadmap

- Regex pre-filtering.
- Sub-prompts for different categories of email.
- Labelling tool call.
