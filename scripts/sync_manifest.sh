#!/usr/bin/env bash
# pull latest, commit local changes, push
git pull --rebase origin master
git add data/captures/*.db
git diff-index --quiet HEAD || git commit -m "auto-sync manifest $(date +%F_%T)"
git push
