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
    import django
    django.setup()

    log("=== Running migrations ===")
    run(f"{manage} migrate --noinput", fatal=True)

    # Ensure django.contrib.sites has the correct Site record (required by allauth)
    log("=== Configuring Site object ===")
    try:
        from django.contrib.sites.models import Site
        domain = os.environ.get('SITE_DOMAIN', 'manifest.docklabs.ai')
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
