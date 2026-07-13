#!/usr/bin/env bash
# Download Maryland Real Property statute sections (official mgaleg PDFs) into
# corpus/statute/. Covers the three titles the RAG advises on:
#   - Title 11B  Maryland Homeowners Association Act
#   - Title 11   Maryland Condominium Act
#   - Title 14   Maryland Contract Lien Act (Subtitle 2)
#
# Source: https://mgaleg.maryland.gov/{SESSION}/Statute_Web/grp/{SECTION}.pdf
# ('grp' = the Real Property article; all three titles live under it.)
#
# Sections are listed explicitly rather than looped, because the code has gaps
# (repealed sections) and decimal sections (e.g. 11B-111.1) that a numeric range
# would miss or 404 on. Missing sections are skipped with a warning, not fatal —
# the statute genuinely changes over time, so a few 404s are expected and fine.
#
# Usage:  ./scripts/download_corpus.sh
# Re-runnable: existing files are skipped unless --force is passed.

set -uo pipefail

SESSION="2022RS"                       # legislative session in the URL path
BASE="https://mgaleg.maryland.gov/${SESSION}/Statute_Web/grp"
OUT="corpus/statute"
SLEEP="0.5"                            # be polite to the state's server
FORCE="${1:-}"

mkdir -p "$OUT"

# --- Title 2: solar collector protection (cross-title, high-demand topic) ---
# §2-119 is the statute that actually governs HOA solar-panel restrictions.
# It lives in Title 2, not 11B, so it must be listed explicitly.
SOLAR=(
  2-119
)

# --- Title 11B: Maryland Homeowners Association Act -------------------------
# 11B-101 .. 11B-118 plus decimal sections added over the years.
HOA=(
  11B-101 11B-102 11B-103 11B-103.1 11B-103.2 11B-104 11B-105 11B-106 11B-106.1
  11B-107 11B-108 11B-109 11B-110 11B-111 11B-111.1 11B-111.2 11B-111.3
  11B-111.4 11B-111.5 11B-111.6 11B-111.7 11B-111.8 11B-111.9
  11B-112 11B-112.1 11B-112.2 11B-112.3 11B-113 11B-113.1 11B-113.2 11B-113.3
  11B-113.4 11B-113.5 11B-113.6 11B-114 11B-115 11B-116 11B-117 11B-118
)

# --- HTML-only sections ----------------------------------------------------
# A few sections are not served as static PDFs at the Statute_Web path but ARE
# available at the dynamic StatuteText endpoint (as HTML, which trafilatura
# extracts cleanly at ingest). 11B-111.10 (dispute settlement / fine process,
# effective Oct 2022) is one of these. Listed separately so the corpus is fully
# reproducible from this script.
HTML_ONLY=(
  11B-111.10
)

# --- Title 11: Maryland Condominium Act ------------------------------------
# 11-101 .. 11-143 plus decimals.
CONDO=(
  11-101 11-102 11-102.1 11-102.2 11-103 11-103.1 11-104 11-105 11-106 11-107
  11-108 11-108.1 11-108.2 11-109 11-109.1 11-109.2 11-109.3 11-110 11-110.1
  11-111 11-111.1 11-111.2 11-111.3 11-112 11-113 11-113.1 11-113.2 11-114
  11-114.1 11-115 11-116 11-117 11-118 11-119 11-120 11-121 11-122 11-123
  11-124 11-125 11-126 11-127 11-128 11-129 11-130 11-131 11-132 11-133
  11-134 11-135 11-136 11-137 11-138 11-139 11-140 11-141 11-142 11-143
)

# --- Title 14, Subtitle 2: Maryland Contract Lien Act ----------------------
LIEN=(
  14-201 14-202 14-203 14-204 14-205 14-206
)

download_one() {
  local section="$1"
  local url="${BASE}/${section}.pdf"
  local dest="${OUT}/md-rp-${section}.pdf"

  if [[ -f "$dest" && "$FORCE" != "--force" ]]; then
    echo "  skip (exists): ${section}"
    return
  fi

  # -f: fail on HTTP errors (404 -> non-zero, so we can warn and continue)
  # -s: quiet, -L: follow redirects
  if curl -fsSL "$url" -o "$dest" 2>/dev/null; then
    # Guard against a 0-byte or HTML error page saved as .pdf
    if [[ -s "$dest" ]] && head -c 5 "$dest" | grep -q '%PDF'; then
      echo "  ok:   ${section}"
    else
      echo "  WARN: ${section} did not return a PDF (removing)"
      rm -f "$dest"
    fi
  else
    echo "  MISS: ${section} (404 or unavailable — likely repealed, skipping)"
  fi
  sleep "$SLEEP"
}

download_one_html() {
  local section="$1"
  local url="https://mgaleg.maryland.gov/mgawebsite/Laws/StatuteText?article=grp&section=${section}&enactments=false"
  local dest="${OUT}/md-rp-${section}.html"

  if [[ -f "$dest" && "$FORCE" != "--force" ]]; then
    echo "  skip (exists): ${section} [html]"
    return
  fi

  if curl -fsSL "$url" -o "$dest" 2>/dev/null; then
    # Sanity-check it contains statute text, not just a nav/error shell.
    if [[ -s "$dest" ]] && grep -qi "Article - Real Property\|§${section}\|this section" "$dest"; then
      echo "  ok:   ${section} [html]"
    else
      echo "  WARN: ${section} html had no statute text (removing)"
      rm -f "$dest"
    fi
  else
    echo "  MISS: ${section} [html] (unavailable, skipping)"
  fi
  sleep "$SLEEP"
}

download_group() {
  local name="$1"; shift
  echo ""
  echo "=== ${name} (${#@} sections) ==="
  for s in "$@"; do
    download_one "$s"
  done
}

echo "Downloading Maryland statute PDFs -> ${OUT}/"
echo "Source: ${BASE}"

download_group "Title 2 - Solar Collector Protection"  "${SOLAR[@]}"
download_group "Title 11B - Homeowners Association Act" "${HOA[@]}"
download_group "Title 11 - Condominium Act"             "${CONDO[@]}"
download_group "Title 14 - Contract Lien Act"           "${LIEN[@]}"

echo ""
echo "=== HTML-only sections (${#HTML_ONLY[@]}) ==="
for s in "${HTML_ONLY[@]}"; do
  download_one_html "$s"
done

echo ""
echo "Done. Downloaded $(find "$OUT" -name '*.pdf' | wc -l | tr -d ' ') PDFs + $(find "$OUT" -name '*.html' | wc -l | tr -d ' ') HTML into ${OUT}/"
echo "Next: uv run mdhpp ingest"
