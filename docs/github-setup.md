# Publishing this project to GitHub

A step-by-step guide written for someone who has never used git from
the command line. Read it once start to finish before doing anything,
then go back and run the commands one at a time.

Total time: about 20 minutes if everything goes smoothly.

---

## Before you start

You need:

- A GitHub account (you said you have one)
- The project on your Mac at `~/Documents/PROJECT26/enterprise-knowledge-assistant`
- Terminal open

You do NOT need:

- A Pro / paid GitHub plan
- Anyone else's permission

---

## Step 1 — Verify git is installed

Open Terminal and run:

```bash
git --version
```

You should see something like `git version 2.39.x`. If you get
"command not found", run `xcode-select --install` and follow the
prompts (this installs Apple's Command Line Developer Tools, which
includes git).

## Step 2 — Tell git who you are

Git stamps every commit with a name and email. Set yours once,
globally, so you don't have to think about it again.

```bash
git config --global user.name "Your Full Name"
git config --global user.email "your-github-email@example.com"
```

Use the same email you sign in to GitHub with. Check it stuck:

```bash
git config --global user.list
```

(or `git config --global -l` on older git).

## Step 3 — Set the default branch name to `main`

Newer git defaults to `main`; older versions still default to
`master`. Be explicit:

```bash
git config --global init.defaultBranch main
```

## Step 4 — Initialize the repository

Move into the project and turn it into a git repo:

```bash
cd ~/Documents/PROJECT26/enterprise-knowledge-assistant
git init
```

You'll see something like `Initialized empty Git repository in
.../enterprise-knowledge-assistant/.git/`. The `.git/` folder is
where git stores its history. Don't touch it manually — ever.

## Step 5 — Verify the gitignore is doing its job

We added `.gitignore` at the start of the project. Check that the
sensitive `.env` file is being excluded:

```bash
git check-ignore -v .env
```

Expected output:

```
.gitignore:14:.env	.env
```

That tells you `.env` is matched by line 14 of `.gitignore`. If the
command prints nothing, your `.env` is NOT being ignored — STOP and
tell me before continuing. We'd be about to commit AWS credentials
to a public repo.

Also verify Docker volumes, build outputs, and node_modules are
ignored:

```bash
git check-ignore -v frontend/node_modules backend/.venv
```

Each should print a `.gitignore:line:pattern` line.

## Step 6 — See what git is about to track

```bash
git status
```

You'll see a long list of untracked files in red. Skim it. Make sure
**`.env` is NOT in the list**. If `.env` shows up there, the
gitignore isn't working — stop and let me know.

## Step 7 — Stage all files for the first commit

```bash
git add .
```

This tells git "include every non-ignored file in the next commit."
Verify what's staged:

```bash
git status
```

You should see a list of files in green. Spot-check that none of
them are:

- `.env`
- Anything with AWS keys
- `node_modules/`
- `.venv/`
- `__pycache__/`

If something sensitive snuck in, run `git reset` to unstage
everything and tell me what you saw. Otherwise continue.

## Step 8 — Make the first commit

```bash
git commit -m "Initial commit"
```

You'll see a summary like `[main (root-commit) abc1234] Initial
commit` followed by `<N> files changed, <M> insertions(+)`. That's
your first save point.

## Step 9 — Create the repository on GitHub

This part happens in your browser, not Terminal.

1. Open <https://github.com/new>
2. **Owner**: your username (default)
3. **Repository name**: `enterprise-knowledge-assistant`
4. **Description**: `Retrieval-augmented question-answering over
   internal documents — Python · FastAPI · React · Postgres + pgvector
   · AWS Bedrock`
5. **Visibility**: choose **Public** so recruiters can see it.
6. Leave every checkbox UNCHECKED. **Do not** initialize with a
   README, .gitignore, or license — your local repo already has all
   three. If you let GitHub create them, you'll get a "non-fast-forward"
   merge conflict on your first push and have to fight it.
7. Click **Create repository**.

You'll land on an empty repo page with instructions like *"…or push
an existing repository from the command line."* Do NOT copy those
yet — we'll do this carefully step by step.

## Step 10 — Generate a Personal Access Token (PAT)

GitHub stopped accepting passwords for git operations in 2021. You
authenticate with a token instead.

1. Open <https://github.com/settings/tokens?type=beta>
2. Click **Generate new token** → **Fine-grained token**
3. **Token name**: `eka-laptop` (or whatever)
4. **Expiration**: 90 days (you can renew later)
5. **Resource owner**: yourself
6. **Repository access**: choose **Only select repositories**, then
   pick `enterprise-knowledge-assistant` from the list
7. **Repository permissions**: scroll down to find **Contents** →
   set to **Read and write**. Leave everything else as default.
8. Click **Generate token**
9. **Copy the token immediately** — it starts with `github_pat_...`.
   You can never see it again after closing this page. Paste it
   somewhere safe (a password manager, ideally) for the next step.

## Step 11 — Add the GitHub repo as a remote

Back in Terminal, in the project folder:

```bash
git remote add origin https://github.com/YOUR-USERNAME/enterprise-knowledge-assistant.git
```

Replace `YOUR-USERNAME` with your actual GitHub username. Verify:

```bash
git remote -v
```

You should see your GitHub URL listed twice (fetch + push).

## Step 12 — Push your code to GitHub

```bash
git branch -M main
git push -u origin main
```

The first push will prompt for credentials:

- **Username**: your GitHub username
- **Password**: paste your **PAT** (the `github_pat_...` token from
  Step 10), NOT your GitHub login password

macOS will offer to remember the credentials in Keychain — say yes.
You won't be prompted again on this machine.

If everything works, you'll see something like:

```
Enumerating objects: ...
Compressing objects: ...
Writing objects: ...
To https://github.com/your-username/enterprise-knowledge-assistant.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main' from 'origin'.
```

## Step 13 — Refresh the GitHub page

Go back to your browser tab on GitHub and refresh. The empty repo is
now full of your code, with the README rendered as the landing page.

## Step 14 — Polish the repo for recruiters

Spend 10 minutes here. It pays off.

### Add the architecture diagram

The README links to `docs/images/system-architecture.png`, which
doesn't exist yet — render it from the Mermaid source:

Option A (use mermaid.live, easiest):

1. Open `docs/diagrams/system-architecture.mmd` in any text editor,
   copy the content
2. Paste into <https://mermaid.live/>
3. Click **Actions** → **PNG** → **Download**
4. Rename the downloaded file to `system-architecture.png` and put
   it in `docs/images/` inside the project folder
5. Repeat for the other three `.mmd` files (`ingestion-flow.png`,
   `query-flow.png`, `deployment-topology.png`)

Option B (CLI):

```bash
npm install -g @mermaid-js/mermaid-cli
cd ~/Documents/PROJECT26/enterprise-knowledge-assistant
mmdc -i docs/diagrams/system-architecture.mmd \
     -o docs/images/system-architecture.png \
     -w 1600 -b transparent
```

### Add screenshots of the running app

While your stack is running (`make up`), take three screenshots:

1. The chat page mid-streaming with the citation panel populated
2. The documents page with sample docs indexed
3. (Optional) The MinIO console showing uploaded files

Save them to `docs/images/` with names like `screenshot-chat.png`,
`screenshot-documents.png`, `screenshot-storage.png`.

### Commit and push the new images

```bash
git add docs/images/
git commit -m "Add architecture diagrams and screenshots"
git push
```

Refresh GitHub — diagrams now render in the README.

### Set repository topics

On the GitHub repo page, click the gear icon next to **About** (top
right). Add these topics:

```
rag retrieval-augmented-generation aws bedrock pgvector
fastapi react typescript hybrid-search vector-search anthropic-claude
```

Topics make your repo discoverable on GitHub search.

### Set the About blurb

In the same panel:

- **Description**: copy the description you set in Step 9
- **Website**: link to your demo video (Loom / YouTube unlisted)
  once recorded
- Check **Releases** off if you don't plan to publish releases

### Pin it to your profile

Go to your GitHub profile page (`https://github.com/YOUR-USERNAME`),
click **Customize your pins**, and pin
`enterprise-knowledge-assistant`. It now appears prominently on your
profile.

---

## Routine git commands you'll use later

When you make changes:

```bash
git status                          # what's changed
git add <file>  OR  git add .       # stage changes
git commit -m "describe the change" # save them locally
git push                            # send to GitHub
```

To see history:

```bash
git log --oneline                   # one-line log
git log --stat                      # what changed in each commit
```

To undo unstaged changes to one file:

```bash
git checkout -- <file>
```

To unstage a file that hasn't been committed:

```bash
git reset <file>
```

If you ever feel lost and want to start a command over, `Ctrl+C`
cancels whatever git is doing.

---

## Common problems

### "fatal: refusing to merge unrelated histories"

You probably initialized the GitHub repo with a README. Easiest fix:

```bash
git pull origin main --allow-unrelated-histories
git push
```

### "Updates were rejected because the remote contains work…"

Same root cause. Same fix.

### Authentication keeps prompting

If macOS Keychain didn't catch the credential, do this once:

```bash
git config --global credential.helper osxkeychain
```

Then push again — Keychain will save the PAT.

### "Permission denied (publickey)"

You added the remote with an SSH URL (`git@github.com:...`) instead
of HTTPS. Fix:

```bash
git remote set-url origin https://github.com/YOUR-USERNAME/enterprise-knowledge-assistant.git
```

Then push again.

### I accidentally committed `.env` with my AWS keys

Stop, don't push if you haven't yet. If you've already pushed:

1. **Rotate the AWS keys immediately** — assume they're compromised.
   In the AWS console go to IAM → your user → Security credentials,
   delete the old access key, create a new one, paste it into `.env`.
2. Remove the file from git history. The simplest tool is
   <https://github.com/newren/git-filter-repo>:

   ```bash
   pip install git-filter-repo
   git filter-repo --path .env --invert-paths
   git push --force
   ```

3. Verify the file is gone from GitHub by browsing the commit history.

The "rotate first" step is non-negotiable. Once a key is on GitHub,
even briefly, treat it as public.

---

## Done

Your project is on GitHub. You can link to it from your résumé,
LinkedIn, and cover letters.
