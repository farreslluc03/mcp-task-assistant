# MCP Task Assistant

A local **Model Context Protocol (MCP) server** for personal task tracking,
built for ENMGT 5405 (Applied AI), Assignment 4.

**Domain:** Personal Productivity (task tracking + email summaries)

It exposes 4 tools and 1 prompt to any MCP client (this README focuses on
Claude Desktop):

| Type   | Name                       | What it does                                                                 |
|--------|----------------------------|-------------------------------------------------------------------------------|
| Tool   | `add_task`                 | Create a task (title, priority, optional due date)                            |
| Tool   | `list_tasks`                | List tasks, filtered by status (`pending`/`done`/`all`) and/or priority       |
| Tool   | `complete_task`             | Mark a task done by its id                                                    |
| Tool   | `send_task_summary_email`   | Email a summary (or save a local draft if no email credentials are set up)    |
| Prompt | `weekly_summary_prompt`     | A reusable instruction template that chains the tools above into a workflow  |

It also implements two security best practices, each with a working exploit
demo proving the protection works - see [Best practices & exploit demos](#best-practices--exploit-demos)
below.

This README assumes you are starting from zero. Follow it top to bottom.

---

## 1. One-time setup: install the tools you need

Open a terminal. In VS Code, you can open one with **Terminal → New Terminal**
(or `` Ctrl+` ``). Every command below is meant to be typed into that
terminal.

### 1.1 Check whether you already have `git`

```bash
git --version
```

Macs almost always already have this. If you see a version number, skip to
1.2. If instead you're prompted to install "Command Line Developer Tools",
click **Install** and wait for it to finish, then re-run the command above.

### 1.2 Install `uv` (the Python environment tool this project uses)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Close and reopen your terminal (or run `source ~/.zshrc`) afterward so your
terminal picks up the new `uv` command. Confirm it worked:

```bash
uv --version
```

### 1.3 Get a GitHub account (skip if you already have one)

Go to [github.com](https://github.com) and sign up. You already have
**GitHub Desktop** installed, which we'll use later to publish this project.

---

## 2. Get the project onto your Mac and open it in VS Code

If you're working with Claude directly on your machine, the project folder
has already been created for you. Otherwise:

1. Open **VS Code**.
2. **File → Open Folder...** and select the `mcp-task-assistant` folder.

You should see this file tree in the Explorer sidebar on the left:

```
mcp-task-assistant/
├── mcp_task_assistant/       # the server's source code
│   ├── server.py              # entry point - defines the tools & prompt
│   ├── storage.py              # SQLite task storage (input sanitization lives here)
│   ├── security.py             # the rate limiter
│   ├── email_tool.py           # email sending / draft logic
│   └── config.py               # loads settings & secrets from .env
├── demo/                      # exploit demonstrations (Part 2 of the assignment)
│   ├── exploit_sql_injection.py
│   └── exploit_rate_limit.py
├── tests/
│   └── smoke_test.py          # quick sanity check that every tool works
├── requirements.txt
├── .env.example                # template - copy to .env and fill in
├── .gitignore
├── claude_desktop_config.example.json
└── README.md                   # this file
```

---

## 3. Create and activate your virtual environment

A **virtual environment** ("venv") is a private, isolated folder of Python
packages just for this project, so it doesn't interfere with anything else
on your Mac. This is exactly the workflow the assignment wants you to
practice.

In the VS Code terminal, make sure you're inside the project folder, then run:

```bash
cd path/to/mcp-task-assistant   # skip if you're already there
uv venv .venv
source .venv/bin/activate
```

> If you see a Linux-looking `.venv` folder already sitting there from
> earlier testing, that's fine - `uv venv .venv` above recreates it fresh,
> correctly, for your Mac.

After `source .venv/bin/activate`, your terminal prompt should now start
with `(.venv)`. That means the virtual environment is **active** - any
`python` or `pip` command you run now uses this isolated environment. You'll
need to run that `source` command again every time you open a new terminal
tab to work on this project (VS Code will often also offer to do this for
you automatically - accept it if it asks, or select the `.venv` interpreter
via the Python version selector in the bottom-right corner of VS Code).

Now install the project's dependencies into that environment:

```bash
uv pip install -r requirements.txt
```

---

## 4. Configure your secrets (`.env`)

Copy the example environment file:

```bash
cp .env.example .env
```

Open the new `.env` file in VS Code. By default it's set up to run in
**dry-run mode** - the email tool will save summaries as local `.eml` files
under `drafts/` instead of actually sending anything. This is the easiest
way to try everything out, and is enough for the whole assignment.

If you'd like to see a *real* email get sent during your demo, follow the
instructions inside `.env` to create a free Gmail "App Password" and fill in
`SMTP_EMAIL_ADDRESS` / `SMTP_APP_PASSWORD`. This takes about two minutes and
does not touch your normal Google password.

**Never commit `.env` to git** - it's already listed in `.gitignore` for
you, so a normal `git add`/`commit` won't include it.

---

## 5. Run the smoke test (sanity check)

Before wiring this up to Claude Desktop, check that everything works on its
own:

```bash
python tests/smoke_test.py
```

You should see 8 `[PASS]` lines and `RESULT: ALL PASSED`. If anything fails,
re-check steps 3-4 above (most often it means the venv isn't activated, or
`requirements.txt` wasn't installed into it).

---

## 6. Best practices & exploit demos

### Best Practice #1: Input Sanitization

All database access in `mcp_task_assistant/storage.py` uses **parameterized
SQL queries** (`?` placeholders, values passed separately from the query
text) instead of building SQL strings by hand. This makes SQL injection
structurally impossible, regardless of what characters a user (or an LLM)
puts into a task title. Free-choice fields like `priority` and `status` are
also checked against a fixed whitelist before they're used at all.

Run the exploit demo:

```bash
python demo/exploit_sql_injection.py
```

This attacks the real server code with the classic
`'; DROP TABLE tasks; --` payload and shows the table survives untouched -
then, for comparison, runs the *same* payload against a deliberately
vulnerable version of the same query and shows that version's table getting
destroyed. That side-by-side is the "before/after" proof the assignment asks
for.

### Best Practice #2: Rate Limiting

`mcp_task_assistant/security.py` implements a sliding-window rate limiter
applied to `send_task_summary_email`, so at most `EMAIL_RATE_LIMIT_MAX`
emails can be sent within any `EMAIL_RATE_LIMIT_WINDOW_SECONDS`-second
window (defaults: 3 per 60 seconds, configurable in `.env`). This protects
against a compromised/malicious client - or simply an LLM caught in a retry
loop - using this server to send a flood of email.

Run the exploit demo:

```bash
python demo/exploit_rate_limit.py
```

This fires 6 rapid calls at the limiter and shows the first 3 allowed and
the rest cleanly blocked with a clear "try again in N seconds" message,
never reaching the mail server.

---

## 7. Connect this server to Claude Desktop

1. **Install Claude Desktop** if you haven't already: download it from
   [claude.ai/download](https://claude.ai/download) and sign in.

2. Find your project's **absolute path**. In the VS Code terminal (inside
   the project folder):

   ```bash
   pwd
   ```

   Copy that path - you'll need it below. It'll look something like
   `/Users/yourname/Documents/mcp-task-assistant`.

3. Open (or create) Claude Desktop's config file:

   ```bash
   open -e ~/Library/Application\ Support/Claude/claude_desktop_config.json
   ```

   (If that fails because the file doesn't exist yet, create the folder and
   file first: `mkdir -p ~/Library/Application\ Support/Claude && touch ~/Library/Application\ Support/Claude/claude_desktop_config.json`,
   then run the `open -e` command again.)

4. Paste in the following, **replacing `<ABSOLUTE_PATH_TO_PROJECT>` with the
   path you copied in step 2** (both places it appears). This is also saved
   for you as `claude_desktop_config.example.json` in the project folder.

   ```json
   {
     "mcpServers": {
       "task-assistant": {
         "command": "<ABSOLUTE_PATH_TO_PROJECT>/.venv/bin/python",
         "args": ["-m", "mcp_task_assistant.server"],
         "cwd": "<ABSOLUTE_PATH_TO_PROJECT>"
       }
     }
   }
   ```

   If the file already has other `mcpServers` entries in it, just add
   `"task-assistant": { ... }` alongside them instead of replacing the whole
   file.

5. Save the file, then **fully quit and reopen Claude Desktop** (Cmd+Q, then
   relaunch it - closing the window isn't enough).

6. In a new chat, click the tools/hammer icon near the message box. You
   should see **task-assistant** listed with its 4 tools. Try asking:

   > "Add a task: finish my MCP assignment, high priority, due Friday."

   or:

   > "Use the weekly_summary_prompt for my professor and send it to
   > test@example.com."

---

## Code citations

- The overall server shape in `mcp_task_assistant/server.py` - creating a
  `FastMCP(...)` instance, registering functions with `@mcp.tool()` /
  `@mcp.prompt()`, and calling `mcp.run()` under
  `if __name__ == "__main__":` - follows the Quickstart pattern shown in the
  official MCP Python SDK README:
  https://github.com/modelcontextprotocol/python-sdk
  All tool bodies, storage, security, and email logic are original code
  written for this assignment (see inline comments for the reasoning behind
  each security decision).

## Limitations

See the project reflection (submitted separately to Canvas) for a fuller
discussion. In short: the rate limiter is in-memory and per-process (fine
for this single-user local server, but would need a shared store like Redis
for a multi-process deployment), and the task list has no per-user
separation since this server is designed to run locally for one person.
