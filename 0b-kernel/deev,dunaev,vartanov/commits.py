"""
python3 commits.py ~/hse/linux -o signed_commits.csv
"""

import argparse
import csv
import subprocess
import sys
from pathlib import Path

FIELD_SEP = "\x1f"  # unit separator
RECORD_SEP = "\x1e"  # record separator

GIT_FORMAT = (
    "%H"  # commit hash
    f"{FIELD_SEP}%an"  # author name
    f"{FIELD_SEP}%ae"  # author email
    f"{FIELD_SEP}%ad"  # author date (we'll control date format with --date)
    f"{FIELD_SEP}%G?"  # signature status (G,B,U,X,N etc.)
    f"{FIELD_SEP}%GS"  # signer name (from signature, if any)
    f"{FIELD_SEP}%GK"  # key used to sign (key id)
    f"{FIELD_SEP}%GG"  # raw verification message from gpg (may contain newlines)
    f"{RECORD_SEP}"
)


def run_git_log(repo_path, number):
    cmd = [
        "git",
        "-C",
        str(repo_path),
        "log",
        "-n",
        str(number),
        "--pretty=format:" + GIT_FORMAT,
        "--date=iso-strict",
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as err:
        print(
            "git log error:",
            err.output.decode(errors="replace"),
        )
        raise
    return out.decode("utf-8", errors="replace")


def sanitize_field(s):
    if s is None:
        return ""
    # Replace newlines and separators to keep CSV tidy
    return (
        s.replace("\r", " ")
        .replace("\n", " ")
        .replace(FIELD_SEP, ",")
        .replace(RECORD_SEP, "\n")
        .strip()
    )


def parse_git_output(text):
    records = []
    # split by record separator; last item may be empty
    for raw_rec in text.split(RECORD_SEP):
        if not raw_rec:
            continue
        parts = raw_rec.split(FIELD_SEP)

        if len(parts) < 8:
            parts += [""] * (8 - len(parts))
        (
            commit_hash,
            author_name,
            author_email,
            author_date,
            sig_status,
            signer_name,
            key_id,
            raw_verif,
        ) = parts[:8]
        # sanitize fields
        commit_hash = sanitize_field(commit_hash)
        author_name = sanitize_field(author_name)
        author_email = sanitize_field(author_email)
        author_date = sanitize_field(author_date)
        sig_status = sanitize_field(sig_status)
        signer_name = sanitize_field(signer_name)
        key_id = sanitize_field(key_id)
        raw_verif = sanitize_field(raw_verif)

        records.append(
            {
                "commit_hash": commit_hash,
                "author_name": author_name,
                "author_email": author_email,
                "date_iso": author_date,
                "sig_status": sig_status,
                "signer_name": signer_name,
                "key_id": key_id,
                "verification_text": raw_verif,
            }
        )
    return records


def filter_signed(records):
    # %G? == 'N' means no signature; keep everything else
    return [r for r in records if r.get("sig_status", "N") != "N"]


def best_who_field(rec):
    # prefer signer_name, otherwise author_email, otherwise author_name
    if rec.get("signer_name"):
        return rec["signer_name"]
    if rec.get("author_email"):
        return rec["author_email"]
    return rec.get("author_name", "")


def write_csv(records, out_path):
    fieldnames = [
        "commit_hash",
        "who",
        "who_email",
        "date_iso",
        "sig_status",
        "key_id",
        "verification_text",
    ]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(
                {
                    "commit_hash": r["commit_hash"],
                    "who": best_who_field(r),
                    "who_email": r.get("author_email", ""),
                    "date_iso": r.get("date_iso", ""),
                    "sig_status": r.get("sig_status", ""),
                    "key_id": r.get("key_id", ""),
                    "verification_text": r.get("verification_text", ""),
                }
            )


def main():
    p = argparse.ArgumentParser(description="Export signed commits to CSV")
    p.add_argument("repo", help="path to git repo (use . for current)")
    p.add_argument("-o", "--output", default="commits.csv", help="output CSV file")
    p.add_argument("-n", "--number", default="10000", help="number of commits to check")
    args = p.parse_args()

    repo_path = Path(args.repo)
    if not (repo_path / ".git").exists() and not (repo_path).exists():
        print(f"'{repo_path}' is not a git-repository")
        sys.exit(1)

    print("1/4 run_git_log")
    out = run_git_log(repo_path, args.number)

    print("2/4 parse_git_output")
    recs = parse_git_output(out)

    print("3/4 filter_signed")
    signed = filter_signed(recs)

    print(f"Found {len(signed)} commits with signature (out {len(recs)}).")

    print("4/4 write_csv")
    write_csv(signed, args.output)


if __name__ == "__main__":
    main()
