#!/usr/bin/env python
"""Railway startup script — run migrations, configure site, collectstatic, then gunicorn."""
import os
import subprocess
import sys

os.environ['PYTHONUNBUFFERED'] = '1'


def log(msg):
    print(f"[startup] {msg}", flush=True)


def run(cmd, fatal=False):
    log(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, stdout=sys.stdout, stderr=sys.stderr)
    if result.returncode != 0:
        log(f"Command exited with code {result.returncode}: {cmd}")
        if fatal:
            sys.exit(result.returncode)
        return False
    return True


def main():
    log("=" * 50)
    log("Manifest — Document Signing Platform")
    log("Container starting")
    log("=" * 50)

    port = os.environ.get('PORT', '8080')
    manage = f"{sys.executable} manage.py"

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'manifest_site.settings')

    # Fix migration inconsistency: admin.0001_initial was applied before
    # keel_accounts.0001_initial when AUTH_USER_MODEL was auth.User.
    # Now that AUTH_USER_MODEL is keel_accounts.KeelUser, Django sees admin
    # depending on keel_accounts and refuses to migrate.
    # Fix: un-mark admin.0001_initial so migrate --fake-initial re-applies it.
    keel_needs_real_migrate = False
    log("=== Checking migration consistency ===")
    try:
        import dj_database_url
        _db_url = os.environ.get('DATABASE_URL', '').strip().lstrip('= ')
        if _db_url and '://' in _db_url:
            db_conf = dj_database_url.parse(_db_url, conn_max_age=0)
            import psycopg2
            conn = psycopg2.connect(
                dbname=db_conf['NAME'], user=db_conf['USER'],
                password=db_conf['PASSWORD'], host=db_conf['HOST'],
                port=db_conf['PORT'],
            )
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute("SELECT 1 FROM django_migrations WHERE app='keel_accounts' AND name='0001_initial'")
            keel_applied = cur.fetchone() is not None
            if not keel_applied:
                cur.execute("SELECT count(*) FROM django_migrations")
                total = cur.fetchone()[0]
                if total > 0:
                    log(f"  keel_accounts not yet applied but {total} other migration(s) exist")
                    log("  Will use fake+real strategy to fix consistency")
                    keel_needs_real_migrate = True
                    # Wipe django_migrations so Django doesn't hit the consistency check
                    cur.execute("DELETE FROM django_migrations")
                    log("  Cleared django_migrations table")
            else:
                log("  No inconsistency found")
            cur.close()
            conn.close()
    except Exception as e:
        log(f"  Migration check skipped: {e}")

    import django
    django.setup()

    log("=== Running migrations ===")
    if not keel_needs_real_migrate:
        run(f"{manage} migrate --noinput", fatal=True)
    else:
        # DB was fully migrated under old auth.User, but keel_accounts tables
        # don't exist yet.  Strategy:
        # 1) Fake ALL migrations (DB schema already correct for existing apps)
        # 2) Un-fake keel_accounts, then run those for real (creates tables)
        # 3) Run migrate again to catch anything else
        log("  Step 1: Faking all existing migrations...")
        run(f"{manage} migrate --fake --noinput", fatal=True)
        log("  Step 2: Running keel_accounts migrations for real...")
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM django_migrations WHERE app='keel_accounts'")
        run(f"{manage} migrate keel_accounts --noinput", fatal=True)
        log("  Step 3: Running remaining migrations...")
        run(f"{manage} migrate --noinput", fatal=False)

    # Ensure django.contrib.sites has the correct Site record (required by allauth)
    log("=== Configuring Site object ===")
    try:
        from django.contrib.sites.models import Site
        domain = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'manifest.docklabs.ai')
        site, created = Site.objects.update_or_create(
            id=1, defaults={'domain': domain, 'name': 'Manifest'},
        )
        log(f"  Site {'created' if created else 'updated'}: {site.domain}")
    except Exception as e:
        log(f"  WARNING: Could not configure Site: {e}")

    log("=== Collecting static files ===")
    run(f"{manage} collectstatic --noinput")

    log(f"=== Starting gunicorn on port {port} ===")
    os.execvp("gunicorn", [
        "gunicorn", "manifest_site.wsgi",
        "--bind", f"0.0.0.0:{port}",
        "--workers", "2",
        "--access-logfile", "-",
        "--error-logfile", "-",
        "--timeout", "120",
    ])


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log(f"FATAL ERROR: {e}")
        import traceback
        traceback.print_exc(file=sys.stdout)
        sys.exit(1)
