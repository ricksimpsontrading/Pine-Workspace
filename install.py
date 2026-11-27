#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Pine Workspace installer (macOS first; Windows deferred; Linux not verified).

Run from the DOWNLOADED package folder:  python3 install.py [--target DIR]
The package folder (where this file lives) is distinct from the folder where
Pine Workspace gets installed. On the first run you choose the target folder
(a default is proposed and editable; paths with spaces are fine); the choice
is remembered in ~/.config/pine-workspace/install.json and proposed again on
later runs. An existing installation is detected and never overwritten.

What is installed (corrected 2026-11-13, audit A-02, A-04, A-05, A-06): only
the files listed by the package's core manifest (PWS_DISTRIBUTION.json), after
every one of them has been checked against its SHA-256 — never a Git history,
a remote, a configuration, products or anything else found beside the package.
The installer refuses to run from a folder that is not a package or that is an
installation. The files are copied into a temporary folder next to the target,
configured (`init`, then `git init` when Git works), and only then renamed into
place: an interruption leaves no half-installed target (an interrupted run may
leave a hidden `.<name>.pws-install-<stamp>` folder, reported on the next run).
Every step is checked: a failed `init` installs nothing; a missing or failing
Git is reported as the documented degraded mode.

Standard library only; no network; nothing outside the target folder is
modified except the small record file above.
"""
import argparse
import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path, PurePosixPath

RECORD = Path.home() / ".config" / "pine-workspace" / "install.json"
PACKAGE_DIR = Path(__file__).resolve().parent
MARKER = "PWS_DISTRIBUTION.json"
# PWS_DISTRIBUTION.json is COPIED: it becomes the installed core manifest used by
# `python3 -m tools.pws_workspace upgrade` to detect local modifications later.
# install.py itself is copied too: it belongs to the core manifest, is required
# by `build-distribution` and compared by `upgrade` like every other core file.
# It is only ever RUN from a downloaded package folder, never from inside an
# installation (refused since 2026-11-13).
INSTALL_MARKERS = ("pws.config.json", "tools/pws_workspace/__main__.py")
# signs that the folder holding install.py is an installation, not a package
INSTALLATION_SIGNS = ("pws.config.json", "scripts", ".claude/runtime", "docs/maintenance",
                      ".claude/settings.local.json")
TEXT = {
    "en": {
        "python_old": "Python 3.9 or later is required (found {version}): nothing was installed.",
        "platform_windows": "Windows support is deferred in this version: nothing was installed.",
        "platform_linux": "Linux is not verified for this version; continuing at your own risk.",
        "platform_other": "{system} is not verified for this version; continuing at your own risk.",
        "not_a_package": "install.py must be run from an extracted Pine Workspace package folder ({detail}): nothing was installed.",
        "from_installation": "This folder is an installation, not a downloaded package (it holds {signs}): install.py is only run from a downloaded package. Nothing was installed.",
        "integrity": "The package is incomplete or altered ({count} file(s), e.g. {sample}): nothing was installed. Download it again and check the SHA-256 of the archive (see INSTALL.md).",
        "needs_yes": "No terminal to ask questions: run again with --yes (and --target) to install without confirmation. Nothing was installed.",
        "eof": "Input closed: nothing was installed.",
        "lang_invalid": "Unsupported language {value!r}: answer en or fr.",
        "target_prompt": "Install folder [{default}]: ",
        "lang_prompt": "Language of the conversation and of the menus (en/fr) [{default}]: ",
        "holder_prompt": "Copyright holder for your scripts (leave empty to set later): ",
        "exists_install": "An existing Pine Workspace installation was found at {path}. Nothing was overwritten. To receive this new core version, upgrade it instead: cd \"{path}\" && python3 -m tools.pws_workspace upgrade --from \"{package}\" --plan   (then --apply, then migrate --plan)",
        "exists_other": "The folder {path} exists and is not empty. Choose another folder (nothing was overwritten).",
        "not_a_folder": "{path} exists and is not a folder (or is a broken link). Choose another folder (nothing was overwritten).",
        "inside_package": "The target cannot be the downloaded package folder or be inside it (folder names are compared as the file system sees them, case included). Choose another folder.",
        "not_writable": "Cannot write to {path}: check permissions or choose another folder.",
        "leftover": "An interrupted earlier run left {path}: it is not used; delete it when convenient.",
        "copying": "Installing into {path} …",
        "init_failed": "The first configuration failed ({detail}): nothing was installed.",
        "copy_failed": "Installation failed ({detail}): nothing was installed.",
        "interrupted": "Interrupted: nothing was installed.",
        "preparing": "Preparing the local test components (PineTS, demonstration data, Vela) with npm from the shipped lockfiles…",
        "done": "Installed. Next steps:\n  cd \"{path}\"\n  claude\n  then /pws → Quality / publication → Local test (PineTS): choose a script and the demonstration data, then \"Open the chart\".",
        "skipped_components": "Local test components not prepared (PWS_INSTALL_SKIP_COMPONENTS=1). Prepare them with: python3 -m tools.pws_workspace components prepare --text",
        "partial": "Installed, but the local test components are not all ready (see above). Your installation is usable; the missing part can be resumed at any time.",
        "recorded": "Install path recorded in {record}",
        "record_failed": "Could not record the install path in {record} ({detail}); the installation itself is complete.",
        "git_init": "Git repository initialized (local-first, no remote).",
        "git_missing": "Git not found: installed without a local repository (degraded mode, see the doctor).",
        "git_failed": "Git is present but did not work ({detail}): installed without a local repository (degraded mode, see the doctor).",
        "confirm": "Proceed? [Y/n]: ",
        "aborted": "Aborted. Nothing was installed.",
    },
    "fr": {
        "python_old": "Python 3.9 ou plus récent est requis (version trouvée : {version}) : rien n'a été installé.",
        "platform_windows": "La prise en charge de Windows est différée dans cette version : rien n'a été installé.",
        "platform_linux": "Linux n'est pas vérifié pour cette version ; poursuite à vos risques.",
        "platform_other": "{system} n'est pas vérifié pour cette version ; poursuite à vos risques.",
        "not_a_package": "install.py doit être lancé depuis le dossier extrait d'un paquet Pine Workspace ({detail}) : rien n'a été installé.",
        "from_installation": "Ce dossier est une installation, pas un paquet téléchargé (il contient {signs}) : install.py ne se lance que depuis un paquet téléchargé. Rien n'a été installé.",
        "integrity": "Le paquet est incomplet ou altéré ({count} fichier(s), par exemple {sample}) : rien n'a été installé. Le télécharger de nouveau et vérifier l'empreinte SHA-256 de l'archive (voir INSTALL.md).",
        "needs_yes": "Aucun terminal pour poser les questions : relancer avec --yes (et --target) pour installer sans confirmation. Rien n'a été installé.",
        "eof": "Saisie fermée : rien n'a été installé.",
        "lang_invalid": "Langue non prise en charge {value!r} : répondre en ou fr.",
        "target_prompt": "Dossier d'installation [{default}] : ",
        "lang_prompt": "Langue des échanges et des menus (en/fr) [{default}] : ",
        "holder_prompt": "Titulaire des droits de vos scripts (laisser vide pour plus tard) : ",
        "exists_install": "Une installation Pine Workspace existe déjà dans {path}. Rien n'a été écrasé. Pour recevoir cette nouvelle version du cœur, la mettre à niveau : cd \"{path}\" && python3 -m tools.pws_workspace upgrade --from \"{package}\" --plan   (puis --apply, puis migrate --plan)",
        "exists_other": "Le dossier {path} existe et n'est pas vide. Choisir un autre dossier (rien n'a été écrasé).",
        "not_a_folder": "{path} existe et n'est pas un dossier (ou est un lien cassé). Choisir un autre dossier (rien n'a été écrasé).",
        "inside_package": "Le dossier cible ne peut être ni le paquet téléchargé ni un dossier à l'intérieur (noms comparés comme le système de fichiers les voit, casse comprise). Choisir un autre dossier.",
        "not_writable": "Écriture impossible dans {path} : vérifier les droits ou choisir un autre dossier.",
        "leftover": "Une exécution interrompue a laissé {path} : il n'est pas utilisé ; le supprimer à votre convenance.",
        "copying": "Installation dans {path} …",
        "init_failed": "La première configuration a échoué ({detail}) : rien n'a été installé.",
        "copy_failed": "L'installation a échoué ({detail}) : rien n'a été installé.",
        "interrupted": "Interrompu : rien n'a été installé.",
        "preparing": "Préparation des composants des tests locaux (PineTS, données de démonstration, Vela) avec npm, à partir des lockfiles fournis…",
        "done": "Installé. Étapes suivantes :\n  cd \"{path}\"\n  claude\n  puis /pws → Qualité / publication → Test local (PineTS) : choisissez un script et les données de démonstration, puis « Ouvrir le graphique ».",
        "skipped_components": "Composants des tests locaux non préparés (PWS_INSTALL_SKIP_COMPONENTS=1). Préparez-les avec : python3 -m tools.pws_workspace components prepare --text",
        "partial": "Installé, mais les composants des tests locaux ne sont pas tous prêts (voir ci-dessus). L'installation est utilisable ; la partie manquante peut être reprise à tout moment.",
        "recorded": "Chemin d'installation enregistré dans {record}",
        "record_failed": "Le chemin d'installation n'a pas pu être enregistré dans {record} ({detail}) ; l'installation elle-même est complète.",
        "git_init": "Dépôt Git initialisé (local-first, aucun remote).",
        "git_missing": "Git introuvable : installé sans dépôt local (mode dégradé, voir le diagnostic).",
        "git_failed": "Git est présent mais n'a pas fonctionné ({detail}) : installé sans dépôt local (mode dégradé, voir le diagnostic).",
        "confirm": "Continuer ? [O/n] : ",
        "aborted": "Abandon. Rien n'a été installé.",
    },
}


def t(lang, key, **kw):
    return TEXT.get(lang, TEXT["en"])[key].format(**kw)


def read_record():
    try:
        data = json.loads(RECORD.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_record(data):
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def is_existing_install(path):
    return (path / MARKER).is_file() or any((path / m).exists() for m in INSTALL_MARKERS)


def writable(path):
    probe_dir = path if path.exists() else path.parent
    while not probe_dir.exists() and probe_dir != probe_dir.parent:
        probe_dir = probe_dir.parent
    if not os.access(str(probe_dir), os.W_OK):
        return False
    try:
        fd, tmp = tempfile.mkstemp(prefix=".pws-write-probe", dir=str(probe_dir))
        os.close(fd)
        os.unlink(tmp)
    except OSError:
        return False
    return True


def sha256(path):
    h = hashlib.sha256()
    with open(str(path), "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def safe_relative(rel):
    if not isinstance(rel, str) or not rel or "\\" in rel:
        return False
    p = PurePosixPath(rel)
    return not p.is_absolute() and ".." not in p.parts and "." not in p.parts


def read_manifest(package):
    """(files, problem): the core manifest's {relative path: sha256}."""
    path = package / MARKER
    if path.is_symlink() or not path.is_file():
        return None, "%s missing" % MARKER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, "%s unreadable: %s" % (MARKER, exc)
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict) or not files:
        return None, "%s lists no core file" % MARKER
    return files, None


def integrity_problems(package, files):
    problems = []
    for rel, digest in sorted(files.items()):
        p = package / rel
        if not safe_relative(rel) or not isinstance(digest, str):
            problems.append(rel)
        elif p.is_symlink() or not p.is_file() or sha256(p) != digest:
            problems.append(rel)
    return problems


def same_or_inside(path, folder):
    """True when `path` is `folder` or lies inside it, as the file system sees
    them (case-insensitive volumes, symbolic links): every existing ancestor of
    `path` is compared to `folder` by identity."""
    probe = Path(os.path.realpath(str(path)))   # physical: links and `..` resolved (review RS-05)
    while True:
        if probe.exists():
            try:
                if os.path.samefile(str(probe), str(folder)):
                    return True
            except OSError:
                pass
        if probe.parent == probe:
            return False
        probe = probe.parent


def clean_answer(text):
    """A path typed or dropped into the Terminal: surrounding quotes removed,
    backslash escapes of a drag-and-drop (`My\\ Folder`) undone."""
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    out, i = [], 0
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def ask(prompt):
    return input(prompt)


def leftovers(target):
    parent = target.parent
    if not parent.is_dir():
        return []
    prefix = ".%s.pws-install-" % target.name
    try:
        return sorted(str(p) for p in parent.iterdir() if p.name.startswith(prefix) and p.is_dir())
    except OSError:
        return []


def main(argv=None):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    parser = argparse.ArgumentParser(description="Install Pine Workspace")
    parser.add_argument("--target", help="installation folder (default: proposed interactively)")
    parser.add_argument("--language", choices=("en", "fr"), help="menus/diagnostics language")
    parser.add_argument("--copyright-holder", default=None)
    parser.add_argument("--yes", action="store_true", help="no interactive confirmation")
    args = parser.parse_args(argv)
    lang = args.language or "en"
    if sys.version_info < (3, 9):
        print(t(lang, "python_old", version=platform.python_version()))
        return 2
    interactive = sys.stdin.isatty() and not args.yes
    if not interactive and not args.yes:
        print(t(lang, "needs_yes"))
        return 1

    system = platform.system()
    if system == "Windows":
        print(t(lang, "platform_windows"))
        return 2
    if system == "Linux":
        print(t(lang, "platform_linux"))
    elif system != "Darwin":
        print(t(lang, "platform_other", system=system or "This system"))

    files, problem = read_manifest(PACKAGE_DIR)
    if problem:
        print(t(lang, "not_a_package", detail=problem))
        return 1
    signs = [s for s in INSTALLATION_SIGNS if (PACKAGE_DIR / s).exists()]
    if signs:
        print(t(lang, "from_installation", signs=", ".join(signs)))
        return 1
    bad = integrity_problems(PACKAGE_DIR, files)
    if bad:
        print(t(lang, "integrity", count=len(bad), sample=", ".join(bad[:3])))
        return 1

    record = read_record()
    recorded = record.get("path") if isinstance(record.get("path"), str) and record.get("path").strip() else None
    default_target = recorded or str(Path.home() / "pine-workspace")
    if same_or_inside(Path(default_target).expanduser(), PACKAGE_DIR):
        default_target = str(Path.home() / "Pine Workspace")
    try:
        target_text = args.target
        if not target_text and interactive:
            target_text = clean_answer(ask(t(lang, "target_prompt", default=default_target))) or default_target
        target = Path(target_text or default_target).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
        if interactive and not args.language:
            for _attempt in range(3):
                lang_in = ask(t(lang, "lang_prompt", default=lang)).strip().lower()
                if not lang_in:
                    break
                if lang_in in ("en", "fr"):
                    lang = lang_in
                    break
                print(t(lang, "lang_invalid", value=lang_in))
        holder = args.copyright_holder
        if interactive and holder is None:
            holder = ask(t(lang, "holder_prompt")).strip() or None
    except EOFError:
        print()
        print(t(lang, "eof"))
        return 1

    if same_or_inside(target, PACKAGE_DIR):
        print(t(lang, "inside_package"))
        return 1
    if target.is_symlink() and not target.exists():
        print(t(lang, "not_a_folder", path=target))
        return 1
    if target.exists():
        if not target.is_dir():
            print(t(lang, "not_a_folder", path=target))
            return 1
        if is_existing_install(target):
            print(t(lang, "exists_install", path=target, package=PACKAGE_DIR))
            return 1
        if any(e.name != ".DS_Store" for e in target.iterdir()):
            print(t(lang, "exists_other", path=target))
            return 1
    if not writable(target):
        print(t(lang, "not_writable", path=target))
        return 1
    for left in leftovers(target):
        print(t(lang, "leftover", path=left))
    if interactive:
        try:
            answer = ask(t(lang, "confirm")).strip().lower()
        except EOFError:
            print()
            print(t(lang, "eof"))
            return 1
        if answer not in ("", "y", "yes", "o", "oui"):
            print(t(lang, "aborted"))
            return 1

    print(t(lang, "copying", path=target))
    real_target = Path(os.path.realpath(str(target)))
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    work = real_target.parent / (".%s.pws-install-%s" % (real_target.name, stamp))
    git_message = None
    try:
        real_target.parent.mkdir(parents=True, exist_ok=True)
        work.mkdir()
        for rel in sorted(files):
            dst = work / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(PACKAGE_DIR / rel), str(dst))
            if sha256(dst) != files[rel]:
                raise OSError("copy of %s does not match the manifest" % rel)
        shutil.copy2(str(PACKAGE_DIR / MARKER), str(work / MARKER))
        env = dict(os.environ)
        env.pop("PYTHONSAFEPATH", None)
        init_cmd = [sys.executable, "-m", "tools.pws_workspace", "init", "--language", lang]
        if holder:
            init_cmd.append("--copyright-holder=" + holder)
        init = subprocess.run(init_cmd, cwd=str(work), env=env, capture_output=True, text=True)
        if init.stdout:
            print(init.stdout.rstrip())
        if init.returncode != 0 or not (work / "pws.config.json").is_file():
            detail = (init.stderr or init.stdout or "exit code %s" % init.returncode).strip().splitlines()
            shutil.rmtree(str(work), ignore_errors=True)
            print(t(lang, "init_failed", detail=detail[-1] if detail else "exit code %s" % init.returncode))
            return 1
        if shutil.which("git"):
            g = subprocess.run(["git", "init", "-q", str(work)], capture_output=True, text=True)
            if g.returncode == 0 and (work / ".git").is_dir():
                git_message = t(lang, "git_init")
            else:
                if (work / ".git").exists():
                    shutil.rmtree(str(work / ".git"), ignore_errors=True)
                detail = (g.stderr or g.stdout or "exit code %s" % g.returncode).strip().splitlines()
                git_message = t(lang, "git_failed", detail=detail[0][:160] if detail else "exit code %s" % g.returncode)
        else:
            git_message = t(lang, "git_missing")
        if real_target.exists():
            ds = real_target / ".DS_Store"
            if ds.is_file():
                ds.unlink()
            os.rmdir(str(real_target))
        os.rename(str(work), str(real_target))
    except KeyboardInterrupt:
        shutil.rmtree(str(work), ignore_errors=True)
        print()
        print(t(lang, "interrupted"))
        return 130
    except OSError as exc:
        shutil.rmtree(str(work), ignore_errors=True)
        print(t(lang, "copy_failed", detail=exc))
        return 1
    print(git_message)
    try:
        write_record({"path": str(target), "installed_at_version": (PACKAGE_DIR / "VERSION").read_text(
            encoding="utf-8").strip() if (PACKAGE_DIR / "VERSION").is_file() else None,
            "language": lang})
        print(t(lang, "recorded", record=RECORD))
    except OSError as exc:
        print(t(lang, "record_failed", record=RECORD, detail=exc))
    # local test components (PineTS, demonstration data, Vela): npm ci from the shipped lockfiles,
    # nothing global; a failure never undoes the installation and can be resumed
    if os.environ.get("PWS_INSTALL_SKIP_COMPONENTS") == "1":          # maintainers' tests only, never offered to users
        print(t(lang, "skipped_components"))
        print(t(lang, "done", path=target))
        return 0
    print(t(lang, "preparing"))
    env = dict(os.environ)
    env.pop("PYTHONSAFEPATH", None)
    comp = subprocess.run([sys.executable, "-m", "tools.pws_workspace", "components", "prepare", "--text",
                           "--language", lang], cwd=str(real_target), env=env, capture_output=True, text=True)
    if comp.stdout:
        print(comp.stdout.rstrip())
    if comp.returncode != 0:
        if comp.stderr and not comp.stdout:
            print(comp.stderr.strip().splitlines()[-1])
        print(t(lang, "partial"))
    print(t(lang, "done", path=target))
    return 0 if comp.returncode == 0 else 4


if __name__ == "__main__":
    sys.exit(main())
