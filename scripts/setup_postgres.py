"""Install a project-local-user PostgreSQL runtime without system services.

Windows only. Downloads the official EDB binaries, binds loopback on port 5433,
uses SCRAM authentication and stores data outside OneDrive in LocalAppData.
Existing clusters and .env files are never overwritten.
"""

import os
import secrets
import subprocess
import urllib.request
import zipfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RUNTIME = Path(os.environ["LOCALAPPDATA"]) / "GenFin" / "postgres17"
BINARY_URL = "https://get.enterprisedb.com/postgresql/postgresql-17.11-3-windows-x64-binaries.zip"


def run(*args, **kwargs):
    return subprocess.run(
        [str(arg) for arg in args], check=True, creationflags=subprocess.CREATE_NO_WINDOW, **kwargs
    )


def main():
    RUNTIME.mkdir(parents=True, exist_ok=True)
    binaries = RUNTIME / "pgsql" / "bin"
    if not (binaries / "initdb.exe").exists():
        archive = RUNTIME / "postgresql.zip"
        print("Downloading official PostgreSQL binaries...", flush=True)
        urllib.request.urlretrieve(BINARY_URL, archive)
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.infolist():
                if member.filename.startswith(("pgsql/bin/", "pgsql/lib/", "pgsql/share/")):
                    target = (RUNTIME / member.filename).resolve()
                    if not target.is_relative_to(RUNTIME.resolve()):
                        raise RuntimeError("Unexpected archive path")
                    bundle.extract(member, RUNTIME)
        archive.unlink()
    data_dir = RUNTIME / "data"
    env_file = PROJECT / ".env"
    if data_dir.exists():
        print("Existing PostgreSQL cluster retained.", flush=True)
        return
    if env_file.exists():
        raise RuntimeError(
            "An .env file already exists; use its existing PostgreSQL configuration."
        )
    password = secrets.token_urlsafe(32)
    password_file = RUNTIME / ".init-password"
    try:
        password_file.write_text(password, encoding="utf-8")
        run(
            binaries / "initdb.exe",
            "-D",
            data_dir,
            "-U",
            "genfin",
            "-A",
            "scram-sha-256",
            "--pwfile",
            password_file,
            "--encoding=UTF8",
            "--locale=C",
        )
    finally:
        password_file.unlink(missing_ok=True)
    with (data_dir / "postgresql.conf").open("a", encoding="utf-8") as config:
        config.write("\nlisten_addresses = '127.0.0.1'\nport = 5433\n")
    env_file.write_text(
        f"GENFIN_DEBUG=True\nSECRET_KEY={secrets.token_urlsafe(64)}\nALLOWED_HOSTS=localhost,127.0.0.1,testserver\nPOSTGRES_DB=genfin\nPOSTGRES_USER=genfin\nPOSTGRES_PASSWORD={password}\nPOSTGRES_HOST=127.0.0.1\nPOSTGRES_PORT=5433\nUSE_SQLITE=False\n",
        encoding="utf-8",
    )
    run(binaries / "pg_ctl.exe", "-D", data_dir, "-l", RUNTIME / "postgres.log", "start", "-w")
    child_env = dict(os.environ, PGPASSWORD=password)
    run(
        binaries / "createdb.exe",
        "-h",
        "127.0.0.1",
        "-p",
        "5433",
        "-U",
        "genfin",
        "genfin",
        env=child_env,
    )
    print("PostgreSQL ready on 127.0.0.1:5433. Credentials saved privately in .env.", flush=True)


if __name__ == "__main__":
    main()
