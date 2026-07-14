# OBS account setup (one-time gate)

> **Done.** The project is live at
> [`home:gmipf:media-preservation`](https://build.opensuse.org/project/show/home:gmipf:media-preservation)
> with the `16.0` and `openSUSE_Tumbleweed` repositories (x86_64). This document
> is kept as a record of the setup and as a guide for anyone reproducing it.
>
> Two things worth knowing if you repeat this:
> - **`api.opensuse.org` offers Basic auth only.** SSH-key authentication is not
>   enabled (`WWW-Authenticate: Basic realm="Use your SUSE developer account"`, no
>   `Signature` realm), which is why the web UI has no SSH-key page.
> - **OBS tokens cannot upload anything.** `osc token --operation` only knows
>   `runservice|branch|release|rebuild|workflow` — all of which act on packages
>   that *already exist*. A token can never create or upload a package, so the
>   account password stays necessary for the one-time `osc mkpac` + first commit.
>   Everything *after* that is automated without it: each package commits only its
>   `_service`, and OBS **pulls** the recipe from git, so a scoped `runservice`
>   token is all CI needs. See [README](README.md) → *Automation*.

Nothing in this lane can be published until there is an account on the
[openSUSE Build Service](https://build.opensuse.org/) (OBS) and a home project
with build targets. This is the OBS equivalent of "create the COPR project" /
"create the COPR project" — you only do it once.

Everything in `opensuse/` is already validated locally without an account (all
five specs build in a Leap 16.0 chroot, see [README](README.md)), so this is the
only step that needs a human.

---

## 1. Create the account

OBS logins are **SUSE IDP accounts** — *not* `accounts.opensuse.org`, and not a
separate OBS-only signup. The "Sign Up" link on build.opensuse.org points at:

> <https://idp-portal.suse.com/univention/self-service/#page=createaccount>

1. Open that URL and fill in the self-service form.
2. Confirm the verification e-mail.
3. Go to <https://build.opensuse.org/> → **Log In** and sign in with the new
   account. Accept the terms if prompted.

Pick the username deliberately: it becomes your project namespace forever
(`home:<user>`) and is public.

## 2. Create / open the home project

Once logged in, the left-hand **Places** menu has a **Your Home Project** link.
If the project does not exist yet, OBS offers to create it — accept. The result
is a project named `home:<user>`.

You can keep the packages directly in `home:<user>`, or use a subproject such as
`home:<user>:media-preservation` to keep them separate from unrelated work. Both
work; the subproject only changes the project name you pass to `osc`.

## 3. Add the build targets (repositories)

In the project, open the **Repositories** tab → **Add from a Distribution**, and
enable:

| Distribution        | OBS repository name    | Why |
|---------------------|------------------------|-----|
| openSUSE Leap 16.0  | `16.0`                 | current stable Leap; the target every spec was validated against |
| openSUSE Tumbleweed | `openSUSE_Tumbleweed`  | rolling; stricter second check (newer GCC, newest permissions framework) |

Then use **Edit repository** on each to confirm the architecture is **`x86_64`**
(every spec is `ExclusiveArch: x86_64` — other arches would only produce
"excluded" skips).

> **The repository name matters.** Leap repositories on OBS are named after the
> bare version — `16.0`, not `openSUSE_Leap_16.0`. That string is what you pass
> to `osc build`. (Leap `16.1` is also offered and can be added later.)

## 4. Configure `osc` locally

`osc` is the OBS command-line client (Fedora: `sudo dnf install osc`). Point it
at the OBS API and let it create its config:

```sh
osc -A https://api.opensuse.org ls
```

On first run `osc` prompts interactively for your username, your password, and
which **password store** to use, then writes `~/.config/osc/oscrc`.

Since it prompts for a password, run this in your own interactive shell rather
than through any tool or agent that captures output.

### Credentials hygiene

- **`~/.config/osc/oscrc` contains your OBS credentials.** Never paste it, never
  commit it, never let a tool print it.
- Prefer the desktop **keyring** password store over plaintext when `osc` asks.
  You can change it later:
  ```sh
  osc config https://api.opensuse.org --select-password-store
  osc config https://api.opensuse.org --change-password
  ```
- `osc config --dump` is safe (it omits `pass`/`passx`).
  **`osc config --dump-full` prints the stored password — do not run it.**
- For automation later, prefer a scoped token (`osc token --help`) over the
  account password.

## 5. Verify

```sh
osc -A https://api.opensuse.org ls home:<user>      # lists packages (empty at first)
osc repos home:<user>                               # should list: 16.0 x86_64 / openSUSE_Tumbleweed x86_64
```

If both work, the gate is done.

---

## What happens next

With the account in place, each tool is published with the flow in
[README](README.md) → *Publishing a package*:

```sh
osc checkout home:<user> <tool>
osc service manualrun     # download the upstream assets (hermetic build => no network at build time)
osc addremove
osc build 16.0 x86_64 <tool>.spec   # local chroot build, the `mock` equivalent
osc commit -m "<tool> <version>"
```

Recommended order — `redumper` → `aaru5` → `aaru` / `mpf` → `discimagecreator`
(the only source build, and therefore the hermetic-build gate).

`osc build` needs network (chroot bootstrap + asset download), so run it outside
any command sandbox.
