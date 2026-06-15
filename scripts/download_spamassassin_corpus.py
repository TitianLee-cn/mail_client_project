"""Download and safely extract the official SpamAssassin public corpus."""

import argparse
import tarfile
import urllib.request
from pathlib import Path

BASE_URL = "https://spamassassin.apache.org/old/publiccorpus"
ARCHIVES = (
    "20030228_easy_ham.tar.bz2",
    "20030228_spam.tar.bz2",
)


def _safe_extract(archive, destination):
    destination = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if destination not in target.parents and target != destination:
            raise ValueError(f"Unsafe archive path: {member.name}")
        if member.issym() or member.islnk():
            raise ValueError(f"Archive links are not allowed: {member.name}")
    archive.extractall(destination)


def download_corpus(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for filename in ARCHIVES:
        archive_path = destination / filename
        if not archive_path.exists():
            url = f"{BASE_URL}/{filename}"
            print(f"Downloading {url}")
            urllib.request.urlretrieve(url, archive_path)
        print(f"Extracting {archive_path}")
        with tarfile.open(archive_path, "r:bz2") as archive:
            _safe_extract(archive, destination)
    return destination


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--destination",
        default="data/datasets/spamassassin",
        help="Directory for downloaded and extracted public mail.",
    )
    args = parser.parse_args()
    print(download_corpus(args.destination))


if __name__ == "__main__":
    main()
