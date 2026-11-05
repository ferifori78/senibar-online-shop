#!/bin/sh
# Apply an update tarball on the server.
#
# Run this from /home/senobar AFTER copying senobar-update.tar.gz there.
# It takes a database backup first, because this update adds a column and a
# data step — and an update that changes the schema is the one you cannot
# undo by re-uploading the old files.
#
#   sh deploy-update.sh
#
# Deliberately `set -e`: if the backup fails, nothing after it should run.
set -e

cd /home/senobar

TARBALL=senobar-update.tar.gz
STAMP=$(date +%F-%H%M)

if [ ! -f "$TARBALL" ]; then
    echo "FAIL: $TARBALL is not here. Copy it to /home/senobar first."
    exit 1
fi

# --- 0. Is this the file you just uploaded? ---------------------------------
# Last time an old copy sat on the server and was deployed by mistake. Print
# the size and time so you can compare with what your Mac reported.
echo "== package =="
ls -l "$TARBALL"
echo "   size: $(stat -c%s "$TARBALL" 2>/dev/null || wc -c < "$TARBALL") bytes"
echo

# --- 1. Back up the database ------------------------------------------------
echo "== backing up database =="
docker compose exec -T db pg_dump -U senobar senobar | gzip > "db-before-$STAMP.sql.gz"
echo "   saved: db-before-$STAMP.sql.gz ($(stat -c%s "db-before-$STAMP.sql.gz" 2>/dev/null) bytes)"
echo

# --- 2. Unpack --------------------------------------------------------------
echo "== unpacking =="
tar xzf "$TARBALL"
echo "   done"
echo

# --- 3. Rebuild and restart -------------------------------------------------
echo "== rebuilding =="
docker compose up -d --build
echo

# --- 4. Migrate -------------------------------------------------------------
# New this time. 0007 adds `origin_type` and marks existing blends as
# multi-origin. Without this the API raises "column does not exist" on every
# product request — the site would be down, not merely unchanged.
echo "== migrating =="
docker compose exec -T api python manage.py migrate
echo

# --- 5. Check ---------------------------------------------------------------
echo "== health =="
docker compose ps
echo
echo "-- facets (should list kinds / species / origin_types):"
curl -s localhost/api/products/facets/ | head -c 400
echo
echo
echo "Done. If the facets line above is empty or an error, read:"
echo "  docker compose logs --tail=50 api"
