# Email Agent

Small Python agent that reviews recent Gmail messages with Ollama and sends important ones to Discord as webhook embeds.

## What It Does

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

If you want `.env` auto-loading, also install:

```bash
pip install python-dotenv
```

## Configuration

Set these environment variables (or place them in `.env` if `python-dotenv` is installed):

```env
OLLAMA_CHAT_URL=...
OLLAMA_MODEL=llama3.1
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

## Gmail Setup

1. Enable the Gmail API in Google Cloud.
2. Create an OAuth client for a desktop app.
3. Download the OAuth JSON and save it as `credentials.json` in the project root.
4. On first run, complete the browser auth flow; `token.json` will be created automatically.

## Run

```bash
python main.py
```

Optional: override the message receipt window used for `GmailReader.get_messages(..., time_delta=...)`:

```bash
python main.py --time-delta 30m
python main.py --time-delta 2h
python main.py --time-delta 1d
```

## Current Processing Behavior

- Query starts with: `newer_than("1d").in_("inbox")`.
- Reader fetches up to 50 messages.
- Additional time filter keeps only emails received in the last 2 hours by default (`--time-delta` overrides this).
- Prompt includes sender, subject, snippet, and body preview (first 500 chars).
- After all emails are reviewed, queued embeds are sent to Discord in batches of 10.

## Project Files

- `main.py`: CLI entrypoint and argument parsing.
- `agent.py`: Ollama decision logic, Gmail interactions, and notification orchestration.
- `mail.py`: Gmail auth, query builder, and message wrapper utilities.
- `discord.py`: Discord embed models, payload shaping, webhook send + chunking.

## Notes

- `token.json` and `credentials.json` are local secrets and should not be committed.
- If no emails are marked important, no webhook request is sent.
- You will need to customize prompts for your use case.
