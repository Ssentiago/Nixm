from functools import lru_cache
import os
import shutil
import toml
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import argparse
import os
import sys
from github import Github
from github import Auth

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


@lru_cache(maxsize=None)
def find_root() -> Path:
    current = Path(__file__).parent
    while current != current.parent:
        if (current / ".root").exists():
            return current
        current = current.parent
    raise RuntimeError("Root not found")


def get_binary_name():
    root = find_root()
    cargo_toml_path = root / "nixm-backend" / "Cargo.toml"
    with open(cargo_toml_path, "r") as f:
        cargo_toml = toml.load(f)
    return cargo_toml["package"]["name"]


def main():
    args_parser = argparse.ArgumentParser(description="Release Nixm")
    args_parser.add_argument(
        "--version", type=str, required=True, help="Version to release"
    )
    args = args_parser.parse_args()

    auth = Auth.Token(GITHUB_TOKEN)

    gh = Github(auth=auth)
    repo = gh.get_repo("Ssentiago/Nixm")

    root_folder = find_root()

    backend_folder = root_folder / "nixm-backend"
    frontend_folder = root_folder / "nixm-frontend"

    backend_bin_folder = backend_folder / "target/release/"
    binary_name = get_binary_name()
    backend_binary = backend_bin_folder / binary_name

    temp_folder = root_folder / "temp_release"

    if not temp_folder.exists():
        temp_folder.mkdir()

    print("Creating release artifacts...")

    try:
        os.chdir(frontend_folder)
        subprocess.run(["bun", "run", "build"], check=True)
        shutil.make_archive(temp_folder / "dist", "zip", frontend_folder, "dist")

        os.chdir(backend_folder)
        subprocess.run(["cargo", "build", "--release"], check=True)
        shutil.copy(backend_binary, temp_folder / binary_name)
    except Exception as e:
        print(f"Error during build: {e}")
        shutil.rmtree(temp_folder)
        sys.exit(1)

    print("Uploading GitHub release...")

    try:
        version = args.version

        subprocess.run(["git", "tag", version], check=True)
        subprocess.run(["git", "push", "origin", version], check=True)

        release = repo.create_git_release(
            tag=f"{version}",
            name=f"Release {version}",
            draft=False,
            prerelease=False,
        )

        release.upload_asset(str(temp_folder / "dist.zip"))
        release.upload_asset(str(temp_folder / binary_name))
    except Exception as e:
        print(f"Error during GitHub release: {e}")
        subprocess.run(["git", "tag", "-d", version], check=True)
        subprocess.run(["git", "push", "origin", "--delete", version], check=True)
        sys.exit(1)
    finally:
        shutil.rmtree(temp_folder)

    print(f"Release {version} created successfully!")


if __name__ == "__main__":
    if GITHUB_TOKEN is None:
        print("GITHUB_TOKEN is not set. Please set it in the .env file.")
        sys.exit(1)

    main()
