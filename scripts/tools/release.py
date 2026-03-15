import json
import os
import re
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path
from typing import Callable

import questionary
import semver
import tomlkit
from dotenv import load_dotenv
from github import Auth
from github import Github
from questionary import Choice

load_dotenv()


@lru_cache(maxsize=None)
def find_root() -> Path:
    current = Path(__file__).parent
    while current != current.parent:
        if (current / ".root").exists():
            return current
        current = current.parent
    sys.exit("Root not found")


ROOT = find_root()

BACKEND_CARGO_TOML = ROOT / "nixm-backend" / "Cargo.toml"
FRONTEND_PACKAGE_JSON = ROOT / "nixm-frontend" / "package.json"


def get_binary_name():
    root = find_root()
    cargo_toml_path = root / "nixm-backend" / "Cargo.toml"
    with open(cargo_toml_path, "r") as f:
        cargo_toml = tomlkit.load(f)
    return cargo_toml["package"]["name"]


def get_version_changelog_section(version: str) -> str:
    root = find_root()
    changelog = root / "CHANGELOG.md"

    if not changelog.exists():
        sys.exit(f"Changelog file not found: {changelog}")

    changelog_content = changelog.read_text(encoding="utf-8")

    pattern = rf"^# {re.escape(version)}(.*?)(?=^# |\Z)"

    # versions are going from bottom to top. newest is on top
    match = re.search(pattern, changelog_content, re.DOTALL | re.MULTILINE)

    if match is None or not match.group(1).strip():
        sys.exit(
            f"Changelog section for {version} not found. Please update the changelog."
        )

    return match.group(1)


def build_and_create_release(previous_version: str, new_version: str, changelog: str):
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    auth = Auth.Token(GITHUB_TOKEN)

    gh = Github(auth=auth)
    repo = gh.get_repo("Ssentiago/Nixm")

    backend_folder = ROOT / "nixm-backend"
    frontend_folder = ROOT / "nixm-frontend"

    backend_bin_folder = backend_folder / "target/release/"
    binary_name = get_binary_name()
    backend_binary = (
        backend_folder / "target/x86_64-unknown-linux-gnu/release/" / binary_name
    )

    temp_folder = ROOT / "temp_release"

    if not temp_folder.exists():
        temp_folder.mkdir()

    print("Creating release artifacts...")

    try:
        os.chdir(frontend_folder)
        subprocess.run(["bun", "run", "build"], check=True)
        shutil.make_archive(
            temp_folder / "dist",
            "zip",
            frontend_folder / "dist",
        )

        os.chdir(backend_folder)
        subprocess.run(
            "cross build --release --target x86_64-unknown-linux-gnu --no-default-features",
            check=True,
            shell=True,
        )
        shutil.copy(backend_binary, temp_folder / binary_name)
    except Exception as e:
        shutil.rmtree(temp_folder)
        sys.exit(f"Error during build: {e}")

    print("Uploading GitHub release...")

    try:
        if previous_version:
            full_changelog_url = f"https://github.com/Ssentiago/Nixm/compare/{previous_version}...{new_version}"
            release_body = f"{changelog}\n\nFull changelog: {full_changelog_url}"
        else:
            release_body = changelog
        subprocess.run(["git", "tag", new_version], check=True)
        subprocess.run(["git", "push", "origin", new_version], check=True)

        release = repo.create_git_release(
            tag=f"{new_version}",
            name=f"Release {new_version}",
            message=release_body,
            draft=False,
            prerelease=False,
        )

        release.upload_asset(str(temp_folder / "dist.zip"))
        release.upload_asset(str(temp_folder / binary_name))
    except Exception as e:
        subprocess.run(["git", "tag", "-d", new_version], check=True)
        subprocess.run(["git", "push", "origin", "--delete", new_version], check=True)
        sys.exit(f"Error during GitHub release: {e}")
    finally:
        shutil.rmtree(temp_folder)

    print(f"Release {new_version} created successfully!")


def update_versions_front_and_back(new_version: str):
    if not BACKEND_CARGO_TOML.exists():
        sys.exit(f"Cargo.toml file not found: {BACKEND_CARGO_TOML}")
    if not FRONTEND_PACKAGE_JSON.exists():
        sys.exit(f"package.json not found: {FRONTEND_PACKAGE_JSON}")

    with open(BACKEND_CARGO_TOML, "r+") as f:
        toml = tomlkit.load(f)
        toml["package"]["version"] = new_version
        f.seek(0)
        f.truncate()
        tomlkit.dump(toml, f)

    with open(FRONTEND_PACKAGE_JSON, "r+") as f:
        js = json.load(f)
        js["version"] = new_version
        f.seek(0)
        f.truncate()
        json.dump(js, f, indent=2)


def make_version_validator(
    previous_versions: list[str], current_version: str, is_first_enter: bool
) -> Callable[[str], bool]:
    def inner(version: str) -> bool | str:
        # if empty string, it means that user pressed Enter
        if not version.strip():
            return True

        if not semver.Version.is_valid(version):
            return (
                "Invalid version format. It should be semantic versioning (e.g., 1.2.3)"
            )

        if version in previous_versions:
            return "Version already exists. Please try again."

        if not is_first_enter and semver.Version.parse(version) < semver.Version.parse(
            current_version
        ):
            return f"Version must be greater than current version. Current version is: {current_version}. Please try again."

        return True

    return inner


def input_new_version(
    previous_versions: list[str], current_version: str, is_first_enter
):
    answer = questionary.text(
        "Enter new version number or press Enter to exit: ",
        validate=make_version_validator(
            previous_versions, current_version, is_first_enter
        ),
    ).ask()

    if not answer.strip():
        print("See you later!")
        sys.exit(0)

    return answer


def version_menu(previous_versions: list[str], current_version: str) -> str:
    while True:
        parsed_version = semver.Version.parse(current_version)
        major, minor, patch = (
            parsed_version.major,
            parsed_version.minor,
            parsed_version.patch,
        )

        answer = questionary.select(
            f"Update current version {current_version} or perform other actions: ",
            [
                Choice(f"Patch (bug fixes): {major}.{minor}.{patch + 1}", "1"),
                Choice(f"Minor (new functionality): {major}.{minor + 1}.0", "2"),
                Choice(f"Major (significant changes): {major + 1}.0.0", "3"),
                Choice("Manual update (enter version)", "4"),
                Choice("View previous versions", "5"),
                Choice("Exit", "6"),
            ],
        ).ask()

        if answer is None:  # user pressed Ctrl+C
            print("See you later!")
            sys.exit(0)

        match answer:
            case "1":
                return f"{major}.{minor}.{patch + 1}"
            case "2":
                return f"{major}.{minor + 1}.0"
            case "3":
                return f"{major + 1}.0.0"
            case "4":
                return input_new_version(previous_versions, current_version, False)
            case "5":
                print("Previous versions:")
                print("\n- ".join(previous_versions))
                questionary.text("Press Enter to continue...").ask()
            case "6":
                print("See you later!")
                sys.exit(0)


def get_version() -> tuple[str, str]:
    tag_exec = subprocess.run(["git", "tag"], capture_output=True)
    tag_exec.check_returncode()

    tag_output = tag_exec.stdout.decode("utf-8").strip()
    tag_output = tag_output and tag_output.split("\n") or []

    current_tag = None if len(tag_output) == 0 else tag_output[-1]

    if len(tag_output) == 0:
        version = input_new_version(tag_output, current_tag, True)
        print(version)
        return version, ""

    version = version_menu(tag_output, current_tag)

    return version, current_tag


def main():
    GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

    if GITHUB_TOKEN is None:
        print()
        sys.exit("GITHUB_TOKEN is not set. Please set it in the .env file.")

    while True:
        release_version, previous_version = get_version()

        confirmation = questionary.select(
            f"You entered version {release_version}. Continue?",
            [Choice("Yes", "y"), Choice("No", "n"), Choice("Retry", "r")],
        ).ask()

        match confirmation:
            case "y":
                break
            case "n":
                print("See you later!")
                sys.exit(0)
            case "r":
                pass

    changelog = get_version_changelog_section(release_version)

    update_versions_front_and_back(release_version)

    current_branch = (
        subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], capture_output=True
        )
        .stdout.decode("utf-8")
        .strip()
    )

    if not current_branch in ["main", "master"]:
        sys.exit("Current branch must be 'main' or 'master'")

    subprocess.run("git reset", shell=True, check=True)
    subprocess.run(
        f"git add {BACKEND_CARGO_TOML} {FRONTEND_PACKAGE_JSON}",
        shell=True,
        check=True,
    )
    subprocess.run(
        f'git commit -m "chore: update app version to {release_version}"',
        shell=True,
        check=True,
    )
    subprocess.run(f"git push origin {current_branch}", shell=True, check=True)

    build_and_create_release(previous_version, release_version, changelog)


if __name__ == "__main__":
    main()
