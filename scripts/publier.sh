#!/usr/bin/env bash
# publier.sh — pousse un dépôt vers sa sauvegarde PRIVÉE (tel quel) et sa version PUBLIQUE
# (historique filtré : sans les chemins personnels, adresse e-mail remplacée par celle
# anonyme de GitHub).
#
#   scripts/publier.sh DÉPÔT URL_PRIVÉE URL_PUBLIQUE [CHEMIN_EXCLU…]
#
# Le filtrage est reproductible : les mêmes commits donnent toujours les mêmes commits
# publics, donc chaque publication s'ajoute à la précédente (pas de push forcé). Un commit
# arrivé directement sur le dépôt public (contribution) bloque la publication au lieu
# d'être écrasé : à intégrer d'abord dans le dépôt local.
set -euo pipefail
depot="$(cd "$1" && pwd)"; prive="$2"; public="$3"; shift 3
exclus=("$@")
EMAIL_PUBLIC="${EMAIL_PUBLIC:-257344285+jordanwinner@users.noreply.github.com}"

# git-filter-repo : module Python 3.12 (le python3 du système est plus récent que le module installé)
filter_repo(){
  for py in python3 python3.12 python3.13; do
    "$py" -c 'import git_filter_repo' 2>/dev/null || continue
    "$py" -c 'import sys; sys.argv[0] = "git-filter-repo"; from git_filter_repo import main; main()' "$@"
    return
  done
  echo "publier : git-filter-repo introuvable (pip install --user git-filter-repo)" >&2; return 1
}

branche="$(git -C "$depot" branch --show-current)"
[ -z "$(git -C "$depot" status --porcelain --untracked-files=no)" ] || { echo "publier : modifications non commitées dans $depot" >&2; exit 1; }

echo "◐ $(basename "$depot") → privé"
git -C "$depot" push "$prive" "$branche"

echo "◐ $(basename "$depot") → public (filtré)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git clone -q --no-local --branch "$branche" "$depot" "$tmp/public"
args=()
for c in "${exclus[@]}"; do args+=(--path "$c"); done
# toutes les adresses d'auteur et de committeur deviennent l'adresse anonyme
printf '%s\n' "$(git -C "$depot" log --format='%aN <%aE>%n%cN <%cE>' | sort -u | sed "s/.*<\(.*\)>/Jordan <$EMAIL_PUBLIC> <\1>/")" > "$tmp/mailmap"
( cd "$tmp/public"
  if [ ${#args[@]} -gt 0 ]; then
    filter_repo --quiet --force --invert-paths "${args[@]}" --mailmap "$tmp/mailmap"
  else
    filter_repo --quiet --force --mailmap "$tmp/mailmap"
  fi
  git push "$public" "$branche" )
echo "✓ publié"
